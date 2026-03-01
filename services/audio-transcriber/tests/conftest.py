"""
Configuração do pytest e fixtures compartilhadas - Audio Transcriber
"""
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from typing import Generator

# Importações do projeto
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
        'MAX_FILE_SIZE_MB': '200',
        'MAX_CONCURRENT_JOBS': '5'
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
        input_file="/tmp/test_audio.mp3"
    )


@pytest.fixture
def temp_audio_file() -> Generator[Path, None, None]:
    """Cria arquivo de áudio temporário para testes"""
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
        mp3_header = b'\xff\xfb\x90\x00'
        temp_file.write(mp3_header)
        temp_file.write(b'\x00' * 1000)
        temp_path = Path(temp_file.name)
    
    yield temp_path
    temp_path.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Limpa arquivos temporários após cada teste"""
    yield
    import glob
    for pattern in ["/tmp/test_*.mp3", "/tmp/*_output.mp3"]:
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
