"""
Caso de uso: Transcrever vídeo enviado via upload.
"""
import logging
import time
from pathlib import Path
from typing import Optional

from src.domain.value_objects import UploadedVideoFile
from src.domain.interfaces import (
    ITranscriptionService,
    IStorageService,
    IVideoUploadValidator
)
from src.domain.exceptions import (
    VideoUploadError,
    TranscriptionError,
    StorageError
)
from src.infrastructure.monitoring import (
    upload_requests_total,
    upload_duration_seconds,
    upload_file_size_bytes,
    uploads_in_progress,
    upload_validation_errors,
    upload_video_duration_seconds,
    upload_formats_total,
)

logger = logging.getLogger(__name__)


class TranscribeUploadedVideoUseCase:
    """
    Caso de uso para transcrever vídeo enviado via upload.
    
    Fluxo:
    1. Validar arquivo (formato, tamanho, duração)
    2. Extrair áudio (se for vídeo)
    3. Transcrever áudio
    4. Retornar transcrição
    5. Cleanup de arquivos temporários
    """
    
    def __init__(
        self,
        transcription_service: ITranscriptionService,
        storage_service: IStorageService,
        upload_validator: IVideoUploadValidator
    ):
        """
        Inicializa o caso de uso.
        
        Args:
            transcription_service: Serviço de transcrição
            storage_service: Serviço de armazenamento
            upload_validator: Validador de upload
        """
        self.transcription_service = transcription_service
        self.storage_service = storage_service
        self.upload_validator = upload_validator
    
    async def execute(
        self,
        uploaded_file: UploadedVideoFile,
        model_size: str = "base",
        language: Optional[str] = None,
        max_file_size_mb: float = 2500.0,
        max_duration_seconds: int = 10800,
    ) -> dict:
        """
        Executa a transcrição do vídeo enviado.
        
        Args:
            uploaded_file: Arquivo enviado
            model_size: Tamanho do modelo Whisper
            language: Idioma (None = auto-detect)
            max_file_size_mb: Tamanho máximo do arquivo (MB)
            max_duration_seconds: Duração máxima (segundos)
        
        Returns:
            dict: Transcrição e metadados
        
        Raises:
            VideoUploadError: Erro de validação
            TranscriptionError: Erro na transcrição
            StorageError: Erro de armazenamento
        """
        start_time = time.time()
        file_format = uploaded_file.get_extension()
        file_type = "video" if uploaded_file.is_video() else "audio"
        
        # Incrementar gauge de uploads em progresso
        uploads_in_progress.inc()
        
        try:
            # 1. Validar arquivo
            logger.info(f"Validating uploaded file: {uploaded_file.original_filename}")
            
            try:
                metadata = await self.upload_validator.validate_file(
                    uploaded_file.file_path,
                    max_file_size_mb,
                    max_duration_seconds
                )
            except VideoUploadError as e:
                # Registrar erro de validação
                error_type = type(e).__name__
                upload_validation_errors.labels(
                    error_type=error_type,
                    format=file_format
                ).inc()
                
                upload_requests_total.labels(
                    status='validation_error',
                    format=file_format
                ).inc()
                
                raise
            
            # Registrar métricas de arquivo válido
            upload_file_size_bytes.labels(format=file_format).observe(
                uploaded_file.size_bytes
            )
            
            if metadata.get('duration'):
                upload_video_duration_seconds.labels(format=file_format).observe(
                    metadata['duration']
                )
            
            upload_formats_total.labels(
                format=file_format,
                type=file_type
            ).inc()
            
            # 2. Extrair áudio (se necessário)
            audio_file_path = uploaded_file.file_path
            
            if uploaded_file.is_video():
                logger.info("Extracting audio from video...")
                audio_file_path = await self._extract_audio(uploaded_file.file_path)
            
            # 3. Transcrever
            logger.info(f"Transcribing with model '{model_size}'...")
            
            transcription = await self.transcription_service.transcribe(
                audio_file_path,
                model_size=model_size,
                language=language
            )
            
            # 4. Retornar resultado
            duration = time.time() - start_time
            
            upload_duration_seconds.labels(format=file_format).observe(duration)
            upload_requests_total.labels(
                status='success',
                format=file_format
            ).inc()
            
            logger.info(
                f"Upload transcription completed in {duration:.2f}s "
                f"(file: {uploaded_file.original_filename})"
            )
            
            return {
                'transcription': transcription,
                'metadata': {
                    'original_filename': uploaded_file.original_filename,
                    'file_size_bytes': uploaded_file.size_bytes,
                    'duration_seconds': metadata.get('duration'),
                    'format': file_format,
                    'type': file_type,
                    'has_video': metadata.get('has_video', False),
                    'has_audio': metadata.get('has_audio', False),
                    'video_codec': metadata.get('video_codec'),
                    'audio_codec': metadata.get('audio_codec'),
                    'model_size': model_size,
                    'language': language or 'auto-detect',
                    'processing_time_seconds': duration
                }
            }
        
        except TranscriptionError as e:
            upload_requests_total.labels(
                status='transcription_error',
                format=file_format
            ).inc()
            logger.error(f"Transcription error: {e}")
            raise
        
        except Exception as e:
            upload_requests_total.labels(
                status='error',
                format=file_format
            ).inc()
            logger.error(f"Unexpected error: {e}")
            raise
        
        finally:
            # 5. Cleanup
            uploads_in_progress.dec()
            await self._cleanup_files(uploaded_file.file_path)
    
    async def _extract_audio(self, video_path: Path) -> Path:
        """
        Extrai áudio do vídeo.
        
        Args:
            video_path: Caminho do vídeo
        
        Returns:
            Path: Caminho do arquivo de áudio
        
        Raises:
            StorageError: Erro ao extrair áudio
        """
        try:
            audio_path = video_path.parent / f"{video_path.stem}_audio.wav"
            
            # Usar storage service para extrair áudio
            # (Assumindo que o storage service tem este método)
            import subprocess
            
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-vn',  # Sem vídeo
                '-acodec', 'pcm_s16le',  # Codec de áudio
                '-ar', '16000',  # Sample rate
                '-ac', '1',  # Mono
                str(audio_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutos
            )
            
            if result.returncode != 0:
                raise StorageError(f"FFmpeg error: {result.stderr}")
            
            if not audio_path.exists():
                raise StorageError("Audio file not created")
            
            logger.info(f"Audio extracted: {audio_path}")
            return audio_path
        
        except subprocess.TimeoutExpired:
            raise StorageError("Audio extraction timeout")
        except Exception as e:
            raise StorageError(f"Failed to extract audio: {e}")
    
    async def _cleanup_files(self, file_path: Path):
        """
        Remove arquivos temporários.
        
        Args:
            file_path: Caminho do arquivo para remover
        """
        try:
            # Remover arquivo de vídeo/áudio original
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Removed: {file_path}")
            
            # Remover arquivo de áudio extraído (se existir)
            audio_path = file_path.parent / f"{file_path.stem}_audio.wav"
            if audio_path.exists():
                audio_path.unlink()
                logger.debug(f"Removed: {audio_path}")
        
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
