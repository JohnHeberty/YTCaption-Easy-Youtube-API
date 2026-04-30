"""
Configuracao base para testes do Audio Normalization Service.
"""
import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import asyncio

from common.test_utils.mock_redis import MockRedis
from common.test_utils.mock_celery import mock_celery_app

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.update({
    "ENVIRONMENT": "test",
    "DEBUG": "false",
    "LOG_LEVEL": "DEBUG",
    "REDIS_URL": "redis://localhost:6379/15",
    "CACHE__TTL_HOURS": "1",
    "PROCESSING__MAX_FILE_SIZE_MB": "10",
})

from app.core.config import get_settings
from app.core.models import Job, JobStatus
from app.core.exceptions import (
    AudioNormalizationError,
    JobNotFoundError,
    JobExpiredError,
)


@pytest.fixture(scope="session")
def event_loop():
    """Fixture para loop de eventos assincronos"""
    loop = asyncio.new_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings():
    """Fixture com configuracoes de teste"""
    return get_settings()


@pytest.fixture
def temp_dir():
    """Fixture para diretorio temporario"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def fake_redis():
    """Fake Redis instance from common test utils."""
    return MockRedis.create_fake_redis()


@pytest.fixture
def mock_redis():
    """Mock do Redis para testes unitarios"""
    redis_mock = MagicMock()
    redis_mock.ping.return_value = True
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.setex.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.keys.return_value = []
    redis_mock.info.return_value = {
        "used_memory": 52428800,
        "connected_clients": 1,
        "total_commands_processed": 100,
    }
    return redis_mock


@pytest.fixture
def mock_job_store():
    """Job store backed by fake Redis."""
    from app.infrastructure.redis_store import AudioNormJobStore
    return MockRedis.create_job_store(AudioNormJobStore)


@pytest.fixture
def mock_audio_processor():
    """Mock audio processor."""
    processor = MagicMock()
    processor.process = MagicMock()
    processor.set_job_store = MagicMock()
    return processor


@pytest.fixture
def mock_celery():
    """Mock Celery app."""
    return mock_celery_app()


@pytest.fixture
def app_with_overrides(mock_job_store, mock_audio_processor):
    """FastAPI app with dependency overrides for testing."""
    from app.infrastructure.dependencies import (
        set_job_store_override,
        set_audio_processor_override,
    )
    from app.main import app

    set_job_store_override(mock_job_store)
    set_audio_processor_override(mock_audio_processor)
    yield app
    from app.infrastructure.dependencies import reset_overrides
    reset_overrides()


@pytest.fixture
def client(app_with_overrides):
    """Test client with dependency overrides."""
    from fastapi.testclient import TestClient
    return TestClient(app_with_overrides)


@pytest.fixture
def sample_job():
    """Job de exemplo para testes"""
    return Job.create_new(
        input_file="/tmp/test.mp3",
        isolate_vocals=False,
        remove_noise=True,
        normalize_volume=True,
        convert_to_mono=True,
        apply_highpass_filter=True,
        set_sample_rate_16k=True,
    )


@pytest.fixture
def sample_audio_data():
    """Dados de audio de exemplo para testes"""
    return b"\xff\xfb\x90\x00" + b"\x00" * 1000


@pytest.fixture
def sample_audio_file(temp_dir, sample_audio_data):
    """Arquivo de audio de exemplo"""
    audio_file = temp_dir / "test_audio.mp3"
    audio_file.write_bytes(sample_audio_data)
    return audio_file