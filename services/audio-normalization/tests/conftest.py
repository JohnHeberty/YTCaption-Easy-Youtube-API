"""
Configuração base para testes
"""
import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock
import asyncio

# Adiciona o diretório da aplicação ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuração para testes
os.environ.update({
    "ENVIRONMENT": "test",
    "DEBUG": "false",
    "LOG_LEVEL": "DEBUG",
    "REDIS_URL": "redis://localhost:6379/15",  # DB 15 para testes
    "CACHE__TTL_HOURS": "1",
    "PROCESSING__MAX_FILE_SIZE_MB": "10",
    "SECURITY__ENABLE_FILE_CONTENT_VALIDATION": "true",
    "MONITORING__ENABLE_PROMETHEUS": "false"  # Desabilitado em testes
})

from app.config import get_settings
from app.models import Job, JobStatus
from app.redis_store_new import RedisJobStore
from app.processor_new import AudioProcessor
from app.security_validator import ValidationMiddleware
from app.exceptions import *


@pytest.fixture(scope="session")
def event_loop():
    """Fixture para loop de eventos assíncronos"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings():
    """Fixture com configurações de teste"""
    return get_settings()


@pytest.fixture
def temp_dir():
    """Fixture para diretório temporário"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def mock_redis():
    """Mock do Redis para testes unitários"""
    redis_mock = MagicMock()
    redis_mock.ping.return_value = True
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.delete.return_value = True
    redis_mock.keys.return_value = []
    redis_mock.info.return_value = {
        'used_memory': 52428800,
        'connected_clients': 1,
        'total_commands_processed': 100
    }
    return redis_mock


@pytest.fixture
def job_store(mock_redis):
    """Job store com Redis mockado"""
    store = RedisJobStore("redis://localhost:6379/15")
    store.redis = mock_redis
    store._is_connected = True
    return store


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
        set_sample_rate_16k=True
    )


@pytest.fixture
def audio_processor():
    """Processador de áudio para testes"""
    return AudioProcessor()


@pytest.fixture
def validation_middleware():
    """Middleware de validação para testes"""
    return ValidationMiddleware()


@pytest.fixture
def sample_audio_data():
    """Dados de áudio de exemplo para testes"""
    # MP3 header mínimo para testes
    return b'\xff\xfb\x90\x00' + b'\x00' * 1000


@pytest.fixture
def sample_audio_file(temp_dir, sample_audio_data):
    """Arquivo de áudio de exemplo"""
    audio_file = temp_dir / "test_audio.mp3"
    audio_file.write_bytes(sample_audio_data)
    return audio_file