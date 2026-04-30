"""
Pytest configuration for YouTube Search Service tests
"""
import pytest
import asyncio
from typing import Generator
from unittest.mock import MagicMock

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
    """Job store backed by fake Redis."""
    from app.infrastructure.redis_store import YouTubeSearchJobStore
    return MockRedis.create_job_store(YouTubeSearchJobStore)


@pytest.fixture
def mock_celery():
    """Mock Celery app."""
    return mock_celery_app()


@pytest.fixture
def app_with_overrides(mock_job_store):
    """FastAPI app with dependency overrides for testing."""
    from app.infrastructure.dependencies import set_job_store_override
    from app.main import app

    set_job_store_override(mock_job_store)
    yield app
    from app.infrastructure.dependencies import reset_overrides
    reset_overrides()


@pytest.fixture
def client(app_with_overrides):
    """Test client with dependency overrides."""
    from fastapi.testclient import TestClient
    return TestClient(app_with_overrides)


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
