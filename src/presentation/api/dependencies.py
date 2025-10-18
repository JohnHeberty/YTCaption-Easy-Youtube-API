"""
Dependency Injection Container.
Gerencia a criação e injeção de dependências seguindo SOLID.
"""
from functools import lru_cache
from src.config import settings
from src.domain.interfaces import (
    IVideoDownloader,
    ITranscriptionService,
    IStorageService
)
from src.infrastructure.youtube import YouTubeDownloader
from src.infrastructure.whisper import WhisperTranscriptionService
from src.infrastructure.storage import LocalStorageService
from src.application.use_cases import (
    TranscribeYouTubeVideoUseCase,
    CleanupOldFilesUseCase
)


class Container:
    """Container de injeção de dependências."""
    
    _video_downloader: IVideoDownloader = None
    _transcription_service: ITranscriptionService = None
    _storage_service: IStorageService = None
    
    @classmethod
    def get_video_downloader(cls) -> IVideoDownloader:
        """Obtém instância do downloader de vídeos."""
        if cls._video_downloader is None:
            cls._video_downloader = YouTubeDownloader(
                max_filesize=settings.max_video_size_mb * 1024 * 1024,
                timeout=settings.download_timeout
            )
        return cls._video_downloader
    
    @classmethod
    def get_transcription_service(cls) -> ITranscriptionService:
        """Obtém instância do serviço de transcrição."""
        if cls._transcription_service is None:
            cls._transcription_service = WhisperTranscriptionService(
                model_name=settings.whisper_model,
                device=settings.whisper_device
            )
        return cls._transcription_service
    
    @classmethod
    def get_storage_service(cls) -> IStorageService:
        """Obtém instância do serviço de armazenamento."""
        if cls._storage_service is None:
            cls._storage_service = LocalStorageService(
                base_temp_dir=settings.temp_dir
            )
        return cls._storage_service
    
    @classmethod
    def get_transcribe_use_case(cls) -> TranscribeYouTubeVideoUseCase:
        """Obtém instância do use case de transcrição."""
        return TranscribeYouTubeVideoUseCase(
            video_downloader=cls.get_video_downloader(),
            transcription_service=cls.get_transcription_service(),
            storage_service=cls.get_storage_service(),
            cleanup_after_processing=settings.cleanup_after_processing,
            max_video_duration=settings.max_video_duration_seconds
        )
    
    @classmethod
    def get_cleanup_use_case(cls) -> CleanupOldFilesUseCase:
        """Obtém instância do use case de limpeza."""
        return CleanupOldFilesUseCase(
            storage_service=cls.get_storage_service(),
            max_age_hours=settings.max_temp_age_hours
        )


# Funções de dependência para FastAPI
def get_transcribe_use_case() -> TranscribeYouTubeVideoUseCase:
    """Dependency para FastAPI."""
    return Container.get_transcribe_use_case()


def get_cleanup_use_case() -> CleanupOldFilesUseCase:
    """Dependency para FastAPI."""
    return Container.get_cleanup_use_case()


def get_storage_service() -> IStorageService:
    """Dependency para FastAPI."""
    return Container.get_storage_service()
