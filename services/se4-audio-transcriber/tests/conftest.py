"""
Fixtures e configurações compartilhadas para testes.
"""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Set required env vars before any module imports trigger settings loading
os.environ.setdefault("APP_NAME", "Audio Transcription Service")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/4")

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

# Configure asyncio mode
pytest_plugins = ("pytest_asyncio",)


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
def mock_processor(mock_job_store):
    """Mock transcription processor."""
    processor = MagicMock()
    processor.process = MagicMock()
    processor.job_store = mock_job_store
    processor.model = None  # Required by check_whisper_model health checker
    return processor


@pytest.fixture
def mock_celery():
    """Mock Celery app."""
    return mock_celery_app()


@pytest.fixture
def app_with_overrides(mock_job_store, mock_processor):
    """FastAPI app with dependency overrides for testing."""
    from app.infrastructure.dependencies import job_store, processor as proc_dep
    from app.main import app

    job_store.set(mock_job_store)
    proc_dep.set(mock_processor)
    try:
        yield app
    finally:
        job_store.reset()
        proc_dep.reset()


@pytest.fixture
def client(app_with_overrides):
    """Test client with dependency overrides."""
    from fastapi.testclient import TestClient
    return TestClient(app_with_overrides)


@pytest.fixture
def mock_redis():
    """Mock Redis client for health checks."""
    redis_mock = MagicMock()
    redis_mock.ping.return_value = True
    return redis_mock


@pytest.fixture
def mock_job_store(mock_redis):
    """Mock do job store implementando IJobStore completo (IJobRepository + IJobQuery)."""
    from datetime import datetime, timedelta, timezone

    _jobs = {}

    async def find_orphaned_jobs(max_age_minutes=30):
        return []

    async def get_queue_info():
        return {"queued": 0, "processing": 0}

    def get_job(job_id):
        return _jobs.get(job_id)

    def save_job(job):
        _jobs[job.id] = job
        return job

    def update_job(job):
        _jobs[job.id] = job
        return job

    def delete_job(job_id):
        if job_id in _jobs:
            del _jobs[job_id]
            return True
        return False

    store = MagicMock()
    # IJobRepository (CRUD)
    store.get_job = MagicMock(side_effect=get_job)
    store.save_job = MagicMock(side_effect=save_job)
    store.update_job = MagicMock(side_effect=update_job)
    store.delete_job = MagicMock(side_effect=delete_job)
    # IJobQuery (read-only queries + aggregation)
    store.list_jobs = MagicMock(return_value=[])
    store.get_stats = MagicMock(return_value={"total_jobs": 0, "by_status": {}})
    store.find_orphaned_jobs = find_orphaned_jobs
    store.get_queue_info = get_queue_info
    # IJobStore (.redis escape hatch — required by health check)
    store.redis = mock_redis
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


def pytest_configure(config):
    """Register custom pytest marks to avoid PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers", "resilience: resilience tests"
    )
    config.addinivalue_line(
        "markers", "circuit_breaker: circuit breaker behavior tests"
    )
    config.addinivalue_line(
        "markers", "error_handling: error handling and corrupted file tests"
    )
    config.addinivalue_line(
        "markers", "real: real (non-mocked) integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: slow-running tests"
    )
    config.addinivalue_line(
        "markers", "integration: integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: unit tests"
    )


@pytest.fixture(autouse=True)
def mock_now_brazil(monkeypatch):
    """Mock para now_brazil() retornar datetime consistente."""
    from datetime import datetime, timezone
    
    fixed_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    def mock_now():
        return fixed_now
    
    monkeypatch.setattr("common.datetime_utils.now_brazil", mock_now)
    return fixed_now
