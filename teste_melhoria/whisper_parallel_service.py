"""
Whisper Parallel Transcription Service - EXPERIMENTAL
Implementação de transcrição paralela dividindo áudio em chunks.
"""
import asyncio
import subprocess
import time
from pathlib import Path
from typing import Optional, List, Dict
from concurrent.futures import ProcessPoolExecutor
import whisper
import torch
from loguru import logger

from src.domain.interfaces import ITranscriptionService
from src.domain.entities import Transcription, VideoFile
from src.domain.value_objects import TranscriptionSegment
from src.domain.exceptions import TranscriptionError


def _transcribe_chunk_worker(
    model_name: str,
    device: str,
    audio_path: str,
    start_time: float,
    end_time: float,
    language: Optional[str],
    chunk_index: int
) -> Dict:
    """
    Worker function para transcrever um chunk de áudio.
    Executado em processo separado para true paralelismo.
    """
    try:
        # Carregar modelo no processo worker
        model = whisper.load_model(model_name, device=device)
        
        # Carregar áudio completo e extrair chunk
        audio = whisper.load_audio(audio_path)
        sample_rate = 16000
        
        # Calcular índices de samples
        start_sample = int(start_time * sample_rate)
        end_sample = int(end_time * sample_rate)
        
        # Extrair chunk
        audio_chunk = audio[start_sample:end_sample]
        
        # Transcrever chunk
        options = {
            'task': 'transcribe',
            'verbose': False,
            'fp16': device == "cuda",
        }
        
        if language and language != "auto":
            options['language'] = language
        
        result = model.transcribe(audio_chunk, **options)
        
        # Ajustar timestamps dos segmentos para posição real no áudio original
        adjusted_segments = []
        for seg in result.get('segments', []):
            adjusted_segments.append({
                'text': seg['text'].strip(),
                'start': seg['start'] + start_time,
                'end': seg['end'] + start_time,
            })
        
        return {
            'chunk_index': chunk_index,
            'segments': adjusted_segments,
            'language': result.get('language', 'unknown'),
            'start_time': start_time,
            'end_time': end_time,
        }
        
    except Exception as e:
        logger.error(f"Error transcribing chunk {chunk_index}: {str(e)}")
        return {
            'chunk_index': chunk_index,
            'error': str(e),
            'segments': [],
            'start_time': start_time,
            'end_time': end_time,
        }


class WhisperParallelTranscriptionService(ITranscriptionService):
    """
    Serviço de transcrição paralela usando chunks de áudio.
    EXPERIMENTAL - Para comparação de performance.
    """
    
    def __init__(
        self,
        model_name: str = "base",
        device: Optional[str] = None,
        num_workers: Optional[int] = None,
        chunk_duration_seconds: int = 120  # 2 minutos por chunk
    ):
        """
        Inicializa o serviço de transcrição paralela.
        
        Args:
            model_name: Nome do modelo Whisper
            device: cpu ou cuda
            num_workers: Número de workers paralelos (None = auto-detect)
            chunk_duration_seconds: Duração de cada chunk em segundos
        """
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.num_workers = num_workers or torch.get_num_threads()
        self.chunk_duration = chunk_duration_seconds
        self._model: Optional[whisper.Whisper] = None
        
        logger.info(
            f"Parallel Whisper service initialized: "
            f"model={model_name}, device={self.device}, "
            f"workers={self.num_workers}, chunk_duration={chunk_duration_seconds}s"
        )
    
    def _get_audio_duration(self, audio_path: Path) -> float:
        """
        Obtém duração do áudio usando FFprobe.
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(audio_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            duration = float(result.stdout.strip())
            return duration
            
        except Exception as e:
            logger.warning(f"Failed to get audio duration: {e}")
            # Fallback: carregar áudio e calcular
            audio = whisper.load_audio(str(audio_path))
            return len(audio) / 16000  # 16kHz sample rate
    
    def _split_audio_chunks(self, duration: float) -> List[tuple]:
        """
        Calcula os chunks de áudio.
        
        Returns:
            Lista de tuplas (start_time, end_time)
        """
        chunks = []
        current_time = 0.0
        
        while current_time < duration:
            end_time = min(current_time + self.chunk_duration, duration)
            chunks.append((current_time, end_time))
            current_time = end_time
        
        logger.info(
            f"Audio split into {len(chunks)} chunks "
            f"(~{self.chunk_duration}s each)"
        )
        
        return chunks
    
    async def transcribe(
        self,
        video_file: VideoFile,
        language: str = "auto"
    ) -> Transcription:
        """
        Transcreve áudio dividindo em chunks paralelos.
        """
        try:
            start_total = time.time()
            
            logger.info(f"[PARALLEL] Starting transcription: {video_file.file_path.name}")
            
            if not video_file.exists:
                raise TranscriptionError(f"Video file not found: {video_file.file_path}")
            
            # Usar áudio original (sem normalização para testes sem FFmpeg)
            logger.info("[PARALLEL] Using original audio (FFmpeg not required for testing)...")
            normalized_audio = video_file.file_path
            
            # Obter duração do áudio
            duration = self._get_audio_duration(normalized_audio)
            logger.info(f"[PARALLEL] Audio duration: {duration:.2f}s")
            
            # Dividir em chunks
            chunks = self._split_audio_chunks(duration)
            
            # Limitar workers ao número de chunks
            actual_workers = min(self.num_workers, len(chunks))
            logger.info(f"[PARALLEL] Using {actual_workers} workers for {len(chunks)} chunks")
            
            # Transcrever chunks em paralelo
            logger.info("[PARALLEL] Starting parallel transcription...")
            start_parallel = time.time()
            
            loop = asyncio.get_event_loop()
            
            # Usar ProcessPoolExecutor para true paralelismo
            with ProcessPoolExecutor(max_workers=actual_workers) as executor:
                tasks = []
                
                for idx, (start_time, end_time) in enumerate(chunks):
                    task = loop.run_in_executor(
                        executor,
                        _transcribe_chunk_worker,
                        self.model_name,
                        self.device,
                        str(normalized_audio),
                        start_time,
                        end_time,
                        language if language != "auto" else None,
                        idx
                    )
                    tasks.append(task)
                
                # Aguardar todos os chunks
                results = await asyncio.gather(*tasks)
            
            parallel_time = time.time() - start_parallel
            logger.info(f"[PARALLEL] Parallel transcription completed in {parallel_time:.2f}s")
            
            # Ordenar resultados por chunk_index
            results = sorted(results, key=lambda x: x['chunk_index'])
            
            # Verificar erros
            errors = [r for r in results if 'error' in r]
            if errors:
                error_msg = "; ".join([r['error'] for r in errors])
                raise TranscriptionError(f"Chunk transcription errors: {error_msg}")
            
            # Merge de segmentos
            logger.info("[PARALLEL] Merging segments...")
            transcription = Transcription()
            detected_languages = []
            
            for result in results:
                for seg_data in result['segments']:
                    segment = TranscriptionSegment(
                        text=seg_data['text'],
                        start=seg_data['start'],
                        end=seg_data['end']
                    )
                    transcription.add_segment(segment)
                
                detected_languages.append(result.get('language', 'unknown'))
            
            # Idioma mais comum
            from collections import Counter
            transcription.language = Counter(detected_languages).most_common(1)[0][0]
            
            total_time = time.time() - start_total
            
            logger.info(
                f"[PARALLEL] Transcription completed: "
                f"{len(transcription.segments)} segments, "
                f"language={transcription.language}, "
                f"total_time={total_time:.2f}s, "
                f"parallel_time={parallel_time:.2f}s"
            )
            
            # Cleanup
            if normalized_audio.exists():
                normalized_audio.unlink()
            
            return transcription
            
        except TranscriptionError:
            raise
        except Exception as e:
            logger.error(f"[PARALLEL] Transcription failed: {str(e)}")
            raise TranscriptionError(f"Failed to transcribe video: {str(e)}")
    
    def _normalize_audio(self, input_path: Path) -> Path:
        """
        Normaliza áudio (mesmo método do serviço original).
        """
        try:
            output_path = input_path.parent / f"{input_path.stem}_normalized.wav"
            
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', str(input_path),
                '-ar', '16000',
                '-ac', '1',
                '-c:a', 'pcm_s16le',
                '-y',
                '-loglevel', 'error',
                str(output_path)
            ]
            
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                raise TranscriptionError(f"FFmpeg failed: {result.stderr}")
            
            if not output_path.exists():
                raise TranscriptionError("Normalized audio not created")
            
            return output_path
            
        except Exception as e:
            raise TranscriptionError(f"Audio normalization failed: {str(e)}")
    
    async def detect_language(self, video_file: VideoFile) -> str:
        """Detecta idioma (implementação simplificada)."""
        # Usar primeiro chunk para detectar idioma
        return "auto"
