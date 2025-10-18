"""Domain interfaces package."""
from src.domain.interfaces.video_downloader import IVideoDownloader
from src.domain.interfaces.transcription_service import ITranscriptionService
from src.domain.interfaces.storage_service import IStorageService

__all__ = ["IVideoDownloader", "ITranscriptionService", "IStorageService"]
