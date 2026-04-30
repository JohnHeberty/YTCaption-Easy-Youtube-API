"""
Fixtures e configurações compartilhadas para testes.
"""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from common.test_utils.mock_redis import MockRedis
from common.test_utils.mock_celery import mock_celery_app

# Adiciona app ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Importa now_brazil antes de usar nas fixtures
try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import datetime
    def now_brazil():
        return datetime.now()


@pytest.fixture
def fake_redis():
    """Fake Redis instance from common test utils."""
    return MockRedis.create_fake_redis()


@pytest.fixture
def mock_job_store_with_fake_redis():
    """Job store backed by fake Redis."""
    from app.infrastructure.redis_store import RedisJobStore
    return MockRedis.create_job_store(RedisJobStore)


@pytest.fixture
def mock_processor():
    """Mock transcription processor."""
    processor = MagicMock()
    processor.process = MagicMock()
    processor.job_store = MagicMock()
    return processor


@pytest.fixture
def mock_celery():
    """Mock Celery app."""
    return mock_celery_app()


@pytest.fixture
def app_with_overrides(mock_job_store, mock_processor):
    """FastAPI app with dependency overrides for testing."""
    from app.infrastructure.dependencies import (
        set_job_store_override,
        set_processor_override,
    )
    from app.main import app

    set_job_store_override(mock_job_store)
    set_processor_override(mock_processor)
    yield app
    from app.infrastructure.dependencies import reset_overrides
    reset_overrides()


@pytest.fixture
def client(app_with_overrides):
    """Test client with dependency overrides."""
    from fastapi.testclient import TestClient
    return TestClient(app_with_overrides)


@pytest.fixture
def mock_job_store():
    """Mock do job store."""
    store = MagicMock()
    store.get_job = MagicMock(return_value=None)
    store.save_job = MagicMock()
    store.update_job = MagicMock()
    store.delete_job = MagicMock()
    return store


@pytest.fixture
def sample_job():
    """Job de exemplo para testes."""
    from app.domain.models import Job, JobStatus, WhisperEngine
    
    return Job(
        id="test_job_123",
        input_file="/tmp/test.mp3",
        status=JobStatus.QUEUED,
        operation="transcribe",
        language_in="pt",
        language_out=None,
        engine=WhisperEngine.FASTER_WHISPER,
        filename="test.mp3",
        file_size_input=1024,
        received_at=now_brazil(),
        created_at=now_brazil(),
        expires_at=now_brazil() + __import__("datetime").timedelta(hours=24),
        progress=0.0,
    )


@pytest.fixture
def temp_dirs(tmp_path):
    """Diretórios temporários para testes."""
    return {
        "upload": tmp_path / "uploads",
        "output": tmp_path / "transcriptions",
        "models": tmp_path / "models",
    }


@pytest.fixture(autouse=True)
def mock_now_brazil(monkeypatch):
    """Mock para now_brazil() retornar datetime consistente."""
    from datetime import datetime, timezone
    
    fixed_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    def mock_now():
        return fixed_now
    
    monkeypatch.setattr("common.datetime_utils.now_brazil", mock_now)
    return fixed_now
