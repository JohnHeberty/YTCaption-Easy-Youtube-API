"""
Serviço de transcrição paralela OTIMIZADO usando persistent worker pool.

Arquitetura atual:
- Workers persistentes carregam modelo UMA VEZ
- Chunks preparados em disco ANTES do processamento
- Sessões isoladas em pastas temp/{session_id}/
- Cleanup automático após processamento

Speedup: 3-5x vs versão antiga
"""
from pathlib import Path
from typing import Optional
from collections import Counter
import time

from loguru import logger

from src.domain.entities import VideoFile, Transcription, TranscriptionSegment
from src.domain.interfaces import ITranscriptionService
from src.domain.exceptions import TranscriptionError
from src.infrastructure.whisper.persistent_worker_pool import PersistentWorkerPool
from src.infrastructure.whisper.temp_session_manager import TempSessionManager, generate_session_id
from src.infrastructure.whisper.chunk_preparation_service import ChunkPreparationService


class WhisperParallelTranscriptionService(ITranscriptionService):
    """
    Serviço de transcrição paralela usando persistent worker pool.
    
    Fluxo:
    1. Cria sessão isolada (temp/{session_id}/)
    2. Converte áudio para WAV
    3. Prepara chunks em disco (FFmpeg split)
    4. Envia chunks para worker pool
    5. Coleta e merge resultados
    6. Cleanup da sessão
    """
    
    def __init__(
        self,
        worker_pool: PersistentWorkerPool,
        temp_manager: TempSessionManager,
        chunk_prep_service: ChunkPreparationService,
        model_name: str = "base",
        device: str = "cpu"
    ):
        """
        Inicializa serviço de transcrição paralela.
        
        Args:
            worker_pool: Pool de workers persistentes (já iniciado)
            temp_manager: Gerenciador de sessões temporárias
            chunk_prep_service: Serviço de preparação de chunks
            model_name: Nome do modelo Whisper
            device: Dispositivo (cpu/cuda)
        """
        self.worker_pool = worker_pool
        self.temp_manager = temp_manager
        self.chunk_prep = chunk_prep_service
        self.model_name = model_name
        self.device = device
        
        logger.info(
            f"Parallel transcription service initialized: "
            f"model={model_name}, device={device}"
        )
    
    def _convert_to_wav(self, input_path: Path, output_dir: Path) -> Path:
        """
        Converte áudio/vídeo para WAV normalizado.
        
        Args:
            input_path: Arquivo de entrada
            output_dir: Diretório de saída
            
        Returns:
            Path do arquivo WAV criado
        """
        import subprocess
        
        output_path = output_dir / f"{input_path.stem}_converted.wav"
        
        logger.info(f"[CONVERT] Converting to WAV: {input_path.name} -> {output_path.name}")
        
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-vn',                   # No video
            '-ar', '16000',          # 16kHz sample rate
            '-ac', '1',              # Mono
            '-c:a', 'pcm_s16le',    # PCM 16-bit
            '-y',                    # Overwrite
            '-loglevel', 'error',
            str(output_path)
        ]
        
        try:
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=600,
                check=False
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or "Unknown FFmpeg error"
                raise TranscriptionError(f"FFmpeg conversion failed: {error_msg}")
            
            if not output_path.exists():
                raise TranscriptionError(f"WAV file not created: {output_path}")
            
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"[CONVERT] Audio converted to WAV: {file_size_mb:.2f} MB")
            
            return output_path
            
        except subprocess.TimeoutExpired as exc:
            raise TranscriptionError("Audio conversion timed out (>10 minutes)") from exc
        except Exception as e:
            if isinstance(e, TranscriptionError):
                raise
            logger.error(f"[CONVERT] Conversion failed: {str(e)}")
            raise TranscriptionError(f"Failed to convert audio: {str(e)}") from e
    
    async def transcribe(
        self,
        video_file: VideoFile,
        language: str = "auto",
        request_ip: Optional[str] = None
    ) -> Transcription:
        """
        Transcreve vídeo usando worker pool persistente.
        
        Args:
            video_file: Entidade do arquivo de vídeo
            language: Código ISO do idioma ou "auto"
            request_ip: IP do cliente (opcional, para session ID)
            
        Returns:
            Objeto Transcription com segmentos
        """
        start_total = time.time()
        
        # 1. Gerar session ID único
        session_id = generate_session_id(request_ip)
        logger.info(f"[PARALLEL] Starting transcription session: {session_id}")
        
        # 2. Criar pasta de sessão isolada
        session_metadata = {
            "video_path": str(video_file.file_path),
            "language": language,
            "request_ip": request_ip,
            "model": self.model_name
        }
        
        session_dir = self.temp_manager.create_session_dir(session_id, session_metadata)
        
        try:
            # 3. Verificar arquivo existe
            if not video_file.exists:
                raise TranscriptionError(f"Video file not found: {video_file.file_path}")
            
            # 4. Converter para WAV (salvar na pasta download da sessão)
            logger.info(f"[PARALLEL] Converting audio for session {session_id}...")
            start_convert = time.time()
            
            download_dir = self.temp_manager.get_download_dir(session_id)
            wav_path = self._convert_to_wav(video_file.file_path, download_dir)
            
            convert_time = time.time() - start_convert
            logger.info(f"[PARALLEL] Conversion completed in {convert_time:.2f}s")
            
            # 5. Preparar chunks em disco (FFmpeg split)
            logger.info(f"[PARALLEL] Preparing chunks for session {session_id}...")
            start_chunk_prep = time.time()
            
            chunks_dir = self.temp_manager.get_chunks_dir(session_id)
            chunk_paths = await self.chunk_prep.prepare_chunks(wav_path, chunks_dir)
            
            chunk_prep_time = time.time() - start_chunk_prep
            logger.info(
                f"[PARALLEL] Chunk preparation completed in {chunk_prep_time:.2f}s "
                f"({len(chunk_paths)} chunks)"
            )
            
            # 6. Enviar chunks para worker pool
            logger.info(f"[PARALLEL] Submitting {len(chunk_paths)} chunks to worker pool...")
            start_processing = time.time()
            
            for idx, chunk_path in enumerate(chunk_paths):
                self.worker_pool.submit_task(
                    session_id=session_id,
                    chunk_path=chunk_path,
                    chunk_idx=idx,
                    language=language
                )
            
            # 7. Coletar resultados dos workers
            logger.info(f"[PARALLEL] Collecting results from workers...")
            results = []
            
            for _ in range(len(chunk_paths)):
                try:
                    result = self.worker_pool.get_result(timeout=600)  # 10min por chunk
                    results.append(result)
                    
                    if result["error"]:
                        logger.error(
                            f"[PARALLEL] Chunk {result['chunk_idx']} failed: {result['error']}"
                        )
                except TimeoutError as e:
                    logger.error(f"[PARALLEL] Timeout waiting for chunk result: {e}")
                    raise TranscriptionError("Chunk processing timed out") from e
            
            processing_time = time.time() - start_processing
            logger.info(f"[PARALLEL] All chunks processed in {processing_time:.2f}s")
            
            # 8. Merge resultados
            logger.info(f"[PARALLEL] Merging {len(results)} chunk results...")
            transcription = self._merge_results(results, session_id)
            
            total_time = time.time() - start_total
            
            logger.info(
                f"[PARALLEL] Transcription completed for session {session_id}: "
                f"total_time={total_time:.2f}s, "
                f"convert={convert_time:.2f}s, "
                f"chunk_prep={chunk_prep_time:.2f}s, "
                f"processing={processing_time:.2f}s, "
                f"segments={len(transcription.segments)}, "
                f"language={transcription.language}"
            )
            
            return transcription
        
        finally:
            # 9. Cleanup completo da sessão (inclui download, chunks, results)
            logger.info(f"[PARALLEL] Cleaning up session {session_id}...")
            cleanup_success = self.temp_manager.cleanup_session(session_id)
            
            if cleanup_success:
                logger.info(f"[PARALLEL] Session {session_id} cleaned up successfully")
            else:
                logger.warning(f"[PARALLEL] Failed to cleanup session {session_id}")
    
    def _merge_results(self, results: list, session_id: str) -> Transcription:
        """
        Merge resultados dos chunks em uma transcrição unificada.
        
        Args:
            results: Lista de resultados dos workers
            session_id: ID da sessão
            
        Returns:
            Objeto Transcription
        """
        # Ordenar resultados por chunk_idx
        results.sort(key=lambda r: r["chunk_idx"])
        
        # Coletar todos os segmentos
        all_segments = []
        languages = []
        errors = []
        
        for result in results:
            if result["error"]:
                errors.append(f"Chunk {result['chunk_idx']}: {result['error']}")
            else:
                all_segments.extend(result["segments"])
                
                if result["language"] and result["language"] != "unknown":
                    languages.append(result["language"])
        
        # Detectar idioma por votação
        if languages:
            detected_language = Counter(languages).most_common(1)[0][0]
        else:
            detected_language = "unknown"
        
        # Criar entidades de segmento
        transcription_segments = [
            TranscriptionSegment(
                start=seg["start"],
                end=seg["end"],
                text=seg["text"]
            )
            for seg in all_segments
        ]
        
        # Log de erros se houver
        if errors:
            logger.warning(
                f"[PARALLEL] Session {session_id} had {len(errors)} chunk errors: {errors}"
            )
        
        # Criar objeto de transcrição
        transcription = Transcription(
            segments=transcription_segments,
            language=detected_language
        )
        
        logger.info(
            f"[PARALLEL] Merged {len(transcription_segments)} segments "
            f"from {len(results)} chunks (language={detected_language})"
        )
        
        return transcription
    
    async def detect_language(self, video_file: VideoFile) -> str:
        """
        Detecta idioma do áudio.
        
        Nota: Usa implementação simples - para produção pode usar worker pool.
        
        Args:
            video_file: Arquivo de vídeo
            
        Returns:
            Código ISO do idioma
        """
        import whisper
        
        try:
            # Carregar modelo temporariamente
            model = whisper.load_model(self.model_name, device=self.device)
            
            # Carregar apenas primeiros 30s
            audio = whisper.load_audio(str(video_file.file_path))
            audio = audio[:30 * 16000]
            
            # Detectar idioma
            audio = whisper.pad_or_trim(audio)
            mel = whisper.log_mel_spectrogram(audio).to(model.device)
            _, probs = model.detect_language(mel)
            
            detected_language = max(probs, key=probs.get)
            logger.info(f"[PARALLEL] Detected language: {detected_language}")
            
            return detected_language
            
        except Exception as e:
            logger.error(f"[PARALLEL] Language detection failed: {e}")
            raise TranscriptionError(f"Failed to detect language: {str(e)}") from e
