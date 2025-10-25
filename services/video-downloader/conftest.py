"""
Configuração do pytest e fixtures compartilhadas - Video Downloader
"""
import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Generator

from app.models import Job, JobStatus
from app.redis_store import RedisJobStore
from app.config import get_settings


@pytest.fixture(scope="session")
def event_loop():
    """Cria event loop para toda a sessão de testes"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def settings():
    """Fixture com configurações de teste"""
    with patch.dict('os.environ', {
        'REDIS_URL': 'redis://localhost:6379/15',
        'ENVIRONMENT': 'test',
        'LOG_LEVEL': 'DEBUG',
    }):
        yield get_settings()


@pytest.fixture
def redis_mock():
    """Mock do Redis para testes unitários"""
    mock_redis = Mock()
    mock_redis.ping = Mock(return_value=True)
    mock_redis.set = Mock(return_value=True)
    mock_redis.get = Mock(return_value=None)
    mock_redis.delete = Mock(return_value=1)
    mock_redis.keys = Mock(return_value=[])
    return mock_redis


@pytest.fixture
def sample_job() -> Job:
    """Fixture com job de exemplo"""
    return Job.create_new(
        url="https://youtube.com/watch?v=test123",
        quality="best"
    )


@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Limpa arquivos temporários após cada teste"""
    yield
    import glob
    for pattern in ["/tmp/test_*.mp4", "./cache/test_*"]:
        for file_path in glob.glob(pattern):
            try:
                Path(file_path).unlink()
            except (FileNotFoundError, PermissionError):
                pass


def pytest_configure(config):
    """Configura marcadores personalizados"""
    config.addinivalue_line("markers", "unit: marca testes unitários")
    config.addinivalue_line("markers", "integration: marca testes de integração")
    config.addinivalue_line("markers", "slow: marca testes que demoram mais de 5 segundos")
