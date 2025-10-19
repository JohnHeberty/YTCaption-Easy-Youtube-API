"""
Serviço de transcrição paralela usando OpenAI Whisper com chunks.
Divide o áudio em partes menores e processa em paralelo usando multiprocessing.
"""
from pathlib import Path
from typing import Optional, List, Tuple
from concurrent.futures import ProcessPoolExecutor
import asyncio
import os
import subprocess
from collections import Counter

from loguru import logger
import whisper

from src.domain.entities import VideoFile, Transcription, TranscriptionSegment
from src.domain.interfaces import ITranscriptionService
from src.domain.exceptions import TranscriptionError


def _transcribe_chunk_worker(
    model_name: str,
    device: str,
    audio_path: str,
    chunk_start: float,
    chunk_end: float,
    language: Optional[str] = None
) -> Tuple[List[dict], str, Optional[str]]:
    """
    Worker function para transcrever um chunk de áudio em processo separado.
    
    Args:
        model_name: Nome do modelo Whisper
        device: Dispositivo (cpu/cuda)
        audio_path: Caminho do arquivo de áudio
        chunk_start: Tempo inicial do chunk (segundos)
        chunk_end: Tempo final do chunk (segundos)
        language: Idioma opcional
    
    Returns:
        Tupla (segments, detected_language, error_message)
    """
    try:
        # Carregar modelo no processo worker
        model = whisper.load_model(model_name, device=device)
        
        # Carregar apenas o chunk do áudio
        audio = whisper.load_audio(audio_path)
        sample_rate = 16000  # Whisper sempre usa 16kHz
        
        start_sample = int(chunk_start * sample_rate)
        end_sample = int(chunk_end * sample_rate)
        chunk_audio = audio[start_sample:end_sample]
        
        # Transcrever chunk
        options = {
            "task": "transcribe",
            "language": language if language != "auto" else None,
            "verbose": False
        }
        
        result = model.transcribe(chunk_audio, **options)
        
        # Ajustar timestamps dos segmentos relativos ao chunk
        adjusted_segments = []
        for segment in result["segments"]:
            adjusted_segment = {
                "start": segment["start"] + chunk_start,
                "end": segment["end"] + chunk_start,
                "text": segment["text"]
            }
            adjusted_segments.append(adjusted_segment)
        
        detected_language = result.get("language", "unknown")
        
        return adjusted_segments, detected_language, None
        
    except Exception as e:
        error_msg = f"Chunk {chunk_start:.1f}-{chunk_end:.1f}s failed: {str(e)}"
        logger.error(f"[PARALLEL] {error_msg}")
        return [], "unknown", error_msg


class WhisperParallelTranscriptionService(ITranscriptionService):
    """
    Serviço de transcrição usando Whisper com processamento paralelo por chunks.
    """
    
    def __init__(
        self,
        model_name: str = "base",
        device: str = "cpu",
        num_workers: Optional[int] = None,
        chunk_duration_seconds: int = 120
    ):
        """
        Inicializa o serviço de transcrição paralela.
        
        Args:
            model_name: Nome do modelo Whisper (tiny, base, small, medium, large)
            device: Dispositivo para processamento (cpu ou cuda)
            num_workers: Número de workers paralelos (None = auto-detect)
            chunk_duration_seconds: Duração de cada chunk em segundos
        """
        self.model_name = model_name
        self.device = device
        self.chunk_duration = chunk_duration_seconds
        
        # Auto-detect número de workers
        if num_workers is None:
            cpu_count = os.cpu_count() or 4
            self.num_workers = max(2, min(cpu_count, 8))  # Entre 2 e 8
        else:
            self.num_workers = max(1, num_workers)
        
        logger.info(
            f"Parallel Whisper service initialized: model={model_name}, "
            f"device={device}, workers={self.num_workers}, "
            f"chunk_duration={chunk_duration_seconds}s"
        )
    
    def _convert_to_wav(self, input_path: Path) -> Path:
        """
        Converte qualquer formato de áudio/vídeo para WAV normalizado.
        Garante compatibilidade com Whisper (16kHz, mono, WAV format).
        
        Args:
            input_path: Caminho do arquivo de áudio/vídeo original
            
        Returns:
            Path: Caminho do arquivo WAV normalizado
            
        Raises:
            TranscriptionError: Se a conversão falhar
        """
        try:
            output_path = input_path.parent / f"{input_path.stem}_converted.wav"
            
            logger.info(f"[PARALLEL] Converting to WAV: {input_path.name} -> {output_path.name}")
            
            # Converter qualquer formato para WAV normalizado
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', str(input_path),
                '-vn',                   # No video (apenas áudio)
                '-ar', '16000',          # 16kHz sample rate
                '-ac', '1',              # Mono
                '-c:a', 'pcm_s16le',    # PCM 16-bit (WAV)
                '-y',                    # Overwrite
                '-loglevel', 'error',
                str(output_path)
            ]
            
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutos timeout
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or "Unknown FFmpeg error"
                raise TranscriptionError(f"FFmpeg conversion failed: {error_msg}")
            
            if not output_path.exists():
                raise TranscriptionError(f"Converted WAV file not created: {output_path}")
            
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"[PARALLEL] Audio converted to WAV: {file_size_mb:.2f} MB")
            
            return output_path
            
        except subprocess.TimeoutExpired:
            raise TranscriptionError("Audio conversion timed out (>10 minutes)")
        except Exception as e:
            if isinstance(e, TranscriptionError):
                raise
            logger.error(f"[PARALLEL] Audio conversion failed: {str(e)}")
            raise TranscriptionError(f"Failed to convert audio to WAV: {str(e)}")
    
    def _get_audio_duration(self, audio_path: Path) -> float:
        """
        Obtém a duração do áudio em segundos.
        
        Args:
            audio_path: Caminho do arquivo de áudio
            
        Returns:
            Duração em segundos
        """
        try:
            # Tentar com FFprobe primeiro (mais rápido)
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(audio_path)
                ],
                capture_output=True,
                text=True,
                check=True
            )
            return float(result.stdout.strip())
        except (FileNotFoundError, subprocess.CalledProcessError):
            logger.warning("FFprobe not available - using Whisper to load audio")
            # Fallback: carregar áudio direto (sem FFmpeg)
            try:
                import wave
                with wave.open(str(audio_path), 'rb') as wav_file:
                    frames = wav_file.getnframes()
                    rate = wav_file.getframerate()
                    duration = frames / float(rate)
                    return duration
            except Exception as e:
                logger.error(f"Failed to get audio duration: {e}")
                raise TranscriptionError(f"Failed to get audio duration: {str(e)}")
    
    def _split_audio_chunks(self, duration: float) -> List[Tuple[float, float]]:
        """
        Divide o áudio em chunks.
        
        Args:
            duration: Duração total do áudio em segundos
            
        Returns:
            Lista de tuplas (start_time, end_time)
        """
        chunks = []
        current_time = 0.0
        
        while current_time < duration:
            end_time = min(current_time + self.chunk_duration, duration)
            chunks.append((current_time, end_time))
            current_time = end_time
        
        return chunks
    
    async def transcribe(
        self,
        video_file: VideoFile,
        language: str = "auto"
    ) -> Transcription:
        """
        Transcreve o vídeo usando processamento paralelo por chunks.
        
        Args:
            video_file: Entidade do arquivo de vídeo
            language: Código ISO do idioma ou "auto" para detecção automática
            
        Returns:
            Objeto Transcription com segmentos e metadados
        """
        try:
            logger.info(f"[PARALLEL] Starting transcription: {video_file.file_path.name}")
            
            if not video_file.exists:
                raise TranscriptionError(f"Video file not found: {video_file.file_path}")
            
            # Converter para WAV se necessário
            audio_path = video_file.file_path
            try:
                logger.info("[PARALLEL] Converting audio to WAV format...")
                audio_path = self._convert_to_wav(video_file.file_path)
            except Exception as e:
                logger.warning(f"[PARALLEL] Audio conversion failed - using original: {e}")
                audio_path = video_file.file_path
            
            # Obter duração do áudio
            duration = self._get_audio_duration(audio_path)
            logger.info(f"[PARALLEL] Audio duration: {duration:.2f}s")
            
            # Dividir em chunks
            chunks = self._split_audio_chunks(duration)
            
            # Limitar workers ao número de chunks
            actual_workers = min(self.num_workers, len(chunks))
            logger.info(f"[PARALLEL] Using {actual_workers} workers for {len(chunks)} chunks")
            
            # Transcrever chunks em paralelo
            loop = asyncio.get_event_loop()
            
            with ProcessPoolExecutor(max_workers=actual_workers) as executor:
                # Criar tasks para cada chunk
                tasks = []
                for chunk_start, chunk_end in chunks:
                    task = loop.run_in_executor(
                        executor,
                        _transcribe_chunk_worker,
                        self.model_name,
                        self.device,
                        str(audio_path),
                        chunk_start,
                        chunk_end,
                        language
                    )
                    tasks.append(task)
                
                # Aguardar todos os chunks
                logger.info("[PARALLEL] Processing chunks...")
                results = await asyncio.gather(*tasks)
            
            # Merge dos resultados
            all_segments = []
            languages = []
            errors = []
            
            for segments, detected_lang, error in results:
                if error:
                    errors.append(error)
                else:
                    all_segments.extend(segments)
                    if detected_lang != "unknown":
                        languages.append(detected_lang)
            
            # Detectar idioma por votação
            if languages:
                detected_language = Counter(languages).most_common(1)[0][0]
            else:
                detected_language = language if language != "auto" else "unknown"
            
            logger.info(f"[PARALLEL] Merged {len(all_segments)} segments from {len(chunks)} chunks")
            
            if errors:
                logger.warning(f"[PARALLEL] {len(errors)} chunks failed: {errors}")
            
            # Ordenar segmentos por tempo de início
            all_segments.sort(key=lambda s: s["start"])
            
            # Criar entidades de segmento
            transcription_segments = [
                TranscriptionSegment(
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"]
                )
                for seg in all_segments
            ]
            
            # Criar objeto de transcrição
            transcription = Transcription(
                segments=transcription_segments,
                language=detected_language
            )
            
            logger.info(
                f"[PARALLEL] Transcription completed: {len(transcription_segments)} segments, "
                f"language={detected_language}"
            )
            
            return transcription
            
        except Exception as e:
            logger.error(f"[PARALLEL] Transcription failed: {str(e)}")
            raise TranscriptionError(f"Failed to transcribe video: {str(e)}")
    
    async def detect_language(self, video_file: VideoFile) -> str:
        """
        Detecta o idioma do áudio (simplificado para serviço paralelo).
        
        Args:
            video_file: Entidade do arquivo de vídeo
            
        Returns:
            Código ISO do idioma detectado
        """
        try:
            # Carregar modelo
            model = whisper.load_model(self.model_name, device=self.device)
            
            # Carregar apenas os primeiros 30 segundos
            audio = whisper.load_audio(str(video_file.file_path))
            audio = audio[:30 * 16000]  # 30 segundos
            
            # Detectar idioma
            audio = whisper.pad_or_trim(audio)
            mel = whisper.log_mel_spectrogram(audio).to(model.device)
            _, probs = model.detect_language(mel)
            
            detected_language = max(probs, key=probs.get)
            logger.info(f"[PARALLEL] Detected language: {detected_language}")
            
            return detected_language
            
        except Exception as e:
            logger.error(f"[PARALLEL] Language detection failed: {str(e)}")
            raise TranscriptionError(f"Failed to detect language: {str(e)}")
