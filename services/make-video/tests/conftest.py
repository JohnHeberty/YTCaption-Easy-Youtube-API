"""
Configuração pytest para Make-Video Service.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

from common.test_utils.mock_redis import MockRedis
from common.test_utils.mock_celery import mock_celery_app

# Adicionar app ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

import pytest


@pytest.fixture
def fake_redis():
    """Fake Redis instance from common test utils."""
    return MockRedis.create_fake_redis()


@pytest.fixture
def mock_redis(monkeypatch):
    """Mock básico para Redis."""
    class MockRedisClient:
        def __init__(self):
            self.data = {}

        def get(self, key):
            return self.data.get(key)

        def setex(self, key, seconds, value):
            self.data[key] = value

        def delete(self, key):
            if key in self.data:
                del self.data[key]

        def scan_iter(self, match):
            return []

    return MockRedisClient()


@pytest.fixture
def mock_redis_store():
    """Job store backed by fake Redis."""
    from app.infrastructure.redis_store import MakeVideoJobStore
    return MockRedis.create_job_store(MakeVideoJobStore)


@pytest.fixture
def mock_job_manager():
    """Mock job manager."""
    manager = MagicMock()
    manager.create_job = MagicMock()
    manager.get_job = MagicMock()
    manager.update_job = MagicMock()
    return manager


@pytest.fixture
def mock_celery():
    """Mock Celery app."""
    return mock_celery_app()


@pytest.fixture
def app_with_overrides(mock_redis_store, mock_job_manager):
    """FastAPI app with dependency overrides for testing."""
    from app.infrastructure.dependencies import (
        set_redis_store_override,
        set_job_manager_override,
    )
    from app.main import app

    set_redis_store_override = MagicMock()
    set_job_manager_override = MagicMock()
    yield app
    from app.infrastructure.dependencies import reset_overrides
    reset_overrides()


@pytest.fixture
def client(app_with_overrides):
    """Test client with dependency overrides."""
    from fastapi.testclient import TestClient
    return TestClient(app_with_overrides)


# Marker para testes lentos
def pytest_configure(config):
    """Configura markers personalizados."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
