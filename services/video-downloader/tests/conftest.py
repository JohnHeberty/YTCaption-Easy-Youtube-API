"""Test configuration for Video Downloader Service.

Shared pytest fixtures and configuration.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Generator

from common.test_utils.mock_redis import MockRedis
from common.test_utils.mock_celery import mock_celery_app


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def fake_redis():
    """Provide a fake Redis instance."""
    return MockRedis.create_fake_redis()


@pytest.fixture
def redis_mock():
    """Mock Redis for unit tests."""
    mock_redis = Mock()
    mock_redis.ping = Mock(return_value=True)
    mock_redis.set = Mock(return_value=True)
    mock_redis.get = Mock(return_value=None)
    mock_redis.delete = Mock(return_value=1)
    mock_redis.keys = Mock(return_value=[])
    mock_redis.setex = Mock(return_value=True)
    return mock_redis


@pytest.fixture
def mock_job_store():
    """Job store backed by fake Redis."""
    from app.infrastructure.redis_store import VideoDownloadJobStore
    return MockRedis.create_job_store(VideoDownloadJobStore)


@pytest.fixture
def mock_celery():
    """Mock Celery app."""
    return mock_celery_app()


@pytest.fixture
def mock_downloader():
    """Mock video downloader."""
    dl = MagicMock()
    dl.download = MagicMock()
    dl.get_file_path = MagicMock(return_value=None)
    return dl


@pytest.fixture
def app_with_overrides(mock_job_store, mock_downloader):
    """FastAPI app with dependency overrides for testing."""
    from app.infrastructure.dependencies import (
        set_job_store_override,
        set_downloader_override,
    )
    from app.main import app

    set_job_store_override(mock_job_store)
    set_downloader_override(mock_downloader)
    yield app
    from app.infrastructure.dependencies import reset_overrides
    reset_overrides()


@pytest.fixture
def client(app_with_overrides):
    """Test client with dependency overrides."""
    from fastapi.testclient import TestClient
    return TestClient(app_with_overrides)


@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Clean up temporary files after each test."""
    yield
    import glob
    import os
    for pattern in ["/tmp/test_*.mp4", "./cache/test_*", "./data/cache/test_*"]:
        for file_path in glob.glob(pattern):
            try:
                Path(file_path).unlink()
            except (FileNotFoundError, PermissionError):
                pass


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line("markers", "unit: marks unit tests")
    config.addinivalue_line("markers", "integration: marks integration tests")
    config.addinivalue_line("markers", "slow: marks slow tests (>5 seconds)")
