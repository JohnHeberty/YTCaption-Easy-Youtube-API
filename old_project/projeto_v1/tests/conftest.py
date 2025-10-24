"""
Configuração de fixtures para testes.
"""
import pytest
from unittest.mock import Mock, AsyncMock
from pathlib import Path

from src.domain.interfaces import (
    IVideoDownloader,
    ITranscriptionService,
    IStorageService
)
from src.domain.entities import VideoFile, Transcription
from src.domain.value_objects import YouTubeURL, TranscriptionSegment


@pytest.fixture
def sample_youtube_url() -> YouTubeURL:
    """Fixture com URL de exemplo."""
    return YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


@pytest.fixture
def sample_video_file(tmp_path) -> VideoFile:
    """Fixture com arquivo de vídeo de exemplo."""
    file_path = tmp_path / "test_video.mp4"
    file_path.write_text("fake video content")
    
    return VideoFile(
        file_path=file_path,
        original_url="https://www.youtube.com/watch?v=test",
        file_size_bytes=1024,
        format="mp4"
    )


@pytest.fixture
def sample_transcription() -> Transcription:
    """Fixture com transcrição de exemplo."""
    transcription = Transcription()
    transcription.language = "en"
    
    segment = TranscriptionSegment(
        text="Test transcription",
        start=0.0,
        end=2.0
    )
    transcription.add_segment(segment)
    
    return transcription


@pytest.fixture
def mock_video_downloader() -> Mock:
    """Mock do video downloader."""
    mock = AsyncMock(spec=IVideoDownloader)
    return mock


@pytest.fixture
def mock_transcription_service() -> Mock:
    """Mock do serviço de transcrição."""
    mock = AsyncMock(spec=ITranscriptionService)
    return mock


@pytest.fixture
def mock_storage_service() -> Mock:
    """Mock do serviço de storage."""
    mock = AsyncMock(spec=IStorageService)
    return mock
