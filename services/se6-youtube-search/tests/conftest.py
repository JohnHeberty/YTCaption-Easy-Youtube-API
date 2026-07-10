"""
Pytest configuration for YouTube Search Service tests
"""
import os
import pytest
import asyncio
from typing import Generator
from unittest.mock import MagicMock, patch

# Set required env vars before any module imports trigger settings loading
os.environ.setdefault("APP_NAME", "YouTube Search Service")
os.environ.setdefault("REDIS_URL", "redis://192.168.1.110:6379/6")

from common.test_utils.mock_redis import MockRedis
from common.test_utils.mock_celery import mock_celery_app


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def fake_redis():
    """Fake Redis instance from common test utils."""
    return MockRedis.create_fake_redis()


@pytest.fixture
def mock_job_store():
    """Job store backed by fake Redis — pure mock, no real connections."""
    mock = MagicMock()
    mock.redis = MagicMock()
    mock.redis.ping.return_value = True
    mock.save_job.return_value = True
    mock.get_job.return_value = None
    mock.list_jobs.return_value = []
    mock.delete_job.return_value = True
    mock.get_stats.return_value = {"total_jobs": 0, "by_status": {}}
    mock.start_cleanup_task = MagicMock()
    mock.stop_cleanup_task = MagicMock()
    mock.cleanup_expired = MagicMock(return_value=0)
    return mock


@pytest.fixture
def mock_celery():
    """Mock Celery app."""
    return mock_celery_app()


@pytest.fixture
def app_with_overrides(mock_job_store):
    """FastAPI app with dependency overrides for testing."""
    from app.infrastructure.dependencies import job_store, get_job_store
    from app.main import app

    get_job_store.cache_clear()
    job_store.set(mock_job_store)

    with patch("app.main._get_job_store", return_value=mock_job_store):
        yield app

    job_store.reset()
    get_job_store.cache_clear()


@pytest.fixture
def client(app_with_overrides):
    """Test client with dependency overrides."""
    from fastapi.testclient import TestClient
    from app.core.config import get_settings
    c = TestClient(app_with_overrides)
    c.headers["X-API-Key"] = get_settings().get("api_key", "")
    return c


@pytest.fixture
def sample_video_id():
    """Sample YouTube video ID for testing"""
    return "dQw4w9WgXcQ"


@pytest.fixture
def sample_channel_id():
    """Sample YouTube channel ID for testing"""
    return "UCuAXFkgsw1L7xaCfnd5JJOw"


@pytest.fixture
def sample_playlist_id():
    """Sample YouTube playlist ID for testing"""
    return "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
