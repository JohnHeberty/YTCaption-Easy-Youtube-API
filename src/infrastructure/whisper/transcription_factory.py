"""
Factory para criar instâncias de serviços de transcrição.
Escolhe entre transcrição normal ou paralela baseado nas configurações.
"""
from loguru import logger

from src.config.settings import settings
from src.domain.interfaces import ITranscriptionService
from src.infrastructure.whisper.transcription_service import WhisperTranscriptionService
from src.infrastructure.whisper.parallel_transcription_service import WhisperParallelTranscriptionService


def create_transcription_service() -> ITranscriptionService:
    """
    Cria e retorna uma instância do serviço de transcrição apropriado.
    
    Returns:
        ITranscriptionService: Serviço de transcrição (normal ou paralelo)
    """
    if settings.enable_parallel_transcription:
        logger.info(
            "🚀 Creating PARALLEL transcription service "
            f"(workers={settings.parallel_workers}, "
            f"chunk_duration={settings.parallel_chunk_duration}s)"
        )
        return WhisperParallelTranscriptionService(
            model_name=settings.whisper_model,
            device=settings.whisper_device,
            num_workers=settings.parallel_workers if settings.parallel_workers > 0 else None,
            chunk_duration_seconds=settings.parallel_chunk_duration
        )
    else:
        logger.info("Creating standard transcription service")
        return WhisperTranscriptionService(
            model_name=settings.whisper_model,
            device=settings.whisper_device
        )
