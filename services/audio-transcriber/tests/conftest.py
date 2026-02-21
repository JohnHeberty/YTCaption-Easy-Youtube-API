"""
Configuração global de fixtures para pytest.
Implementa fixtures para testes do Audio Transcriber Service.
"""
import os
import sys
import shutil
import tempfile
from pathlib import Path
from typing import Generator, Dict, List, Any
import pytest
import asyncio

# Adiciona o diretório app ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


# ============================================================================
# CONFIGURAÇÃO DE AMBIENTE
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Configura ambiente de teste antes de todos os testes."""
    os.environ["ENVIRONMENT"] = "test"
    os.environ["REDIS_DB"] = "15"  # Database separada para testes
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["WHISPER_MODEL"] = "base"  # Modelo menor para testes
    os.environ["WHISPER_DEVICE"] = "cpu"
    os.environ["PORT"] = "8099"  # Porta diferente para testes
    yield
    print("\n✅ Ambiente de teste finalizado")


# ============================================================================
# FIXTURES DE DIRETÓRIOS TEMPORÁRIOS
# ============================================================================

@pytest.fixture(scope="function")
def temp_dir() -> Generator[Path, None, None]:
    """Cria diretório temporário para cada teste."""
    tmp = tempfile.mkdtemp(prefix="test_audio_transcriber_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="function")
def test_dirs(temp_dir: Path) -> Dict[str, Path]:
    """Cria estrutura de diretórios para testes."""
    dirs = {
        "uploads": temp_dir / "uploads",
        "transcriptions": temp_dir / "transcriptions",
        "models": temp_dir / "models",
        "temp": temp_dir / "temp",
        "logs": temp_dir / "logs",
    }
    for dir_path in dirs.values():
        dir_path.mkdir(parents=True, exist_ok=True)
    return dirs


# ============================================================================
# FIXTURES DE ÁUDIO
# ============================================================================

@pytest.fixture(scope="session")
def test_audio_ogg() -> Path:
    """Retorna path para arquivo de áudio de teste real (TEST-.ogg)."""
    audio_path = Path(__file__).parent / "TEST-.ogg"
    if not audio_path.exists():
        pytest.skip("Arquivo TEST-.ogg não encontrado")
    return audio_path


@pytest.fixture(scope="function")
def sample_audio_file(temp_dir: Path) -> Path:
    """
    Gera arquivo de áudio sintético para teste usando FFmpeg.
    Áudio de 3 segundos, mono, 16kHz.
    """
    audio_path = temp_dir / "test_audio.wav"
    
    import subprocess
    cmd = [
        "ffmpeg", "-f", "lavfi", "-i",
        "sine=frequency=440:duration=3",
        "-ar", "16000",
        "-ac", "1",
        "-y",
        str(audio_path)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("FFmpeg não disponível para gerar áudio de teste")
    
    return audio_path


@pytest.fixture(scope="function")
def corrupted_audio_file(temp_dir: Path) -> Path:
    """Gera arquivo de áudio corrompido para testes de erro."""
    audio_path = temp_dir / "corrupted.wav"
    audio_path.write_bytes(b"INVALID_AUDIO_DATA" * 100)
    return audio_path


@pytest.fixture(scope="function")
def empty_audio_file(temp_dir: Path) -> Path:
    """Gera arquivo de áudio vazio."""
    audio_path = temp_dir / "empty.wav"
    audio_path.touch()
    return audio_path


# ============================================================================
# FIXTURES DE MODELOS E SERVIÇOS (SEM MOCK)
# ============================================================================

class StubWhisperSegment:
    """Stub para segmento de transcrição Whisper"""
    def __init__(self, start: float, end: float, text: str, words: List[Dict[str, Any]]):
        self.start = start
        self.end = end
        self.text = text
        self.words = words


class StubWhisperModel:
    """Stub do modelo Faster-Whisper (sem Mock)"""
    def transcribe(self, audio_path: str, **kwargs):
        """Retorna transcrição stub"""
        segments = [
            StubWhisperSegment(
                start=0.0,
                end=2.5,
                text="Hello world",
                words=[
                    {"start": 0.0, "end": 0.5, "word": "Hello"},
                    {"start": 0.5, "end": 2.5, "word": "world"}
                ]
            ),
            StubWhisperSegment(
                start=2.5,
                end=5.0,
                text="This is a test",
                words=[
                    {"start": 2.5, "end": 3.0, "word": "This"},
                    {"start": 3.0, "end": 3.5, "word": "is"},
                    {"start": 3.5, "end": 4.0, "word": "a"},
                    {"start": 4.0, "end": 5.0, "word": "test"}
                ]
            )
        ]
        info = {"language": "en", "duration": 5.0}
        return segments, info


@pytest.fixture
def stub_whisper_model():
    """Stub do modelo Faster-Whisper (sem Mock)"""
    return StubWhisperModel()


class StubRedisClient:
    """Stub do cliente Redis (sem Mock)"""
    def __init__(self):
        self.data = {}
    
    def ping(self):
        return True
    
    def get(self, key):
        return self.data.get(key)
    
    def set(self, key, value):
        self.data[key] = value
        return True
    
    def setex(self, key, ttl, value):
        self.data[key] = value
        return True
    
    def exists(self, key):
        return key in self.data
    
    def delete(self, key):
        self.data.pop(key, None)
        return True
    
    def keys(self, pattern):
        # Simple pattern matching
        prefix = pattern.replace('*', '')
        return [k.encode() for k in self.data.keys() if k.startswith(prefix)]
    
    def zadd(self, key, mapping):
        return True
    
    def zcard(self, key):
        return 0
    
    def zremrangebyscore(self, key, min_score, max_score):
        return 0
    
    def zrange(self, key, start, end, withscores=False):
        return []
    
    def zrem(self, key, *members):
        return True
    
    def pipeline(self):
        return StubRedisPipeline(self)


class StubRedisPipeline:
    """Stub do pipeline Redis"""
    def __init__(self, client):
        self.client = client
        self.commands = []
    
    def zremrangebyscore(self, key, min_score, max_score):
        self.commands.append(0)
        return self
    
    def zcard(self, key):
        self.commands.append(0)
        return self
    
    def zadd(self, key, mapping):
        self.commands.append(1)
        return self
    
    def expire(self, key, ttl):
        self.commands.append(1)
        return self
    
    def execute(self):
        return self.commands


@pytest.fixture
def stub_redis_client():
    """Stub do cliente Redis (sem Mock)"""
    return StubRedisClient()


class StubTaskResult:
    """Stub do resultado de task Celery"""
    def __init__(self, task_id: str):
        self.id = task_id


class StubCeleryApp:
    """Stub do Celery app (sem Mock)"""
    def send_task(self, name, args=None, kwargs=None):
        return StubTaskResult("test-task-id")


@pytest.fixture
def stub_celery_app():
    """Stub do Celery app (sem Mock)"""
    return StubCeleryApp()


# ============================================================================
# FIXTURES DE DADOS DE TESTE
# ============================================================================

@pytest.fixture
def sample_transcription_segments():
    """Retorna segmentos de transcrição de exemplo."""
    return [
        {
            "id": 0,
            "seek": 0,
            "start": 0.0,
            "end": 2.5,
            "text": "Hello world",
            "tokens": [1, 2, 3],
            "temperature": 0.0,
            "avg_logprob": -0.5,
            "compression_ratio": 1.2,
            "no_speech_prob": 0.01,
            "words": [
                {"start": 0.0, "end": 0.5, "word": "Hello", "prob": 0.99},
                {"start": 0.5, "end": 2.5, "word": "world", "prob": 0.98}
            ]
        },
        {
            "id": 1,
            "seek": 250,
            "start": 2.5,
            "end": 5.0,
            "text": "This is a test",
            "tokens": [4, 5, 6, 7],
            "temperature": 0.0,
            "avg_logprob": -0.4,
            "compression_ratio": 1.1,
            "no_speech_prob": 0.02,
            "words": [
                {"start": 2.5, "end": 3.0, "word": "This", "prob": 0.97},
                {"start": 3.0, "end": 3.5, "word": "is", "prob": 0.96},
                {"start": 3.5, "end": 4.0, "word": "a", "prob": 0.95},
                {"start": 4.0, "end": 5.0, "word": "test", "prob": 0.94}
            ]
        }
    ]


@pytest.fixture
def sample_job_data():
    """Retorna dados de job de exemplo."""
    return {
        "job_id": "test-job-123",
        "audio_path": "/tmp/test_audio.wav",
        "status": "pending",
        "progress": 0,
        "created_at": "2026-02-21T00:00:00",
        "updated_at": "2026-02-21T00:00:00",
    }


# ============================================================================
# FIXTURES DE API (FastAPI)
# ============================================================================

@pytest.fixture
def test_client():
    """Cliente de teste para FastAPI."""
    from fastapi.testclient import TestClient
    from app.main import app
    
    with TestClient(app) as client:
        yield client


@pytest.fixture
async def async_test_client():
    """Cliente assíncrono de teste para FastAPI."""
    from httpx import AsyncClient
    from app.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# ============================================================================
# FIXTURES DE CONFIGURAÇÃO
# ============================================================================

@pytest.fixture
def test_config():
    """Configuração de teste."""
    return {
        "whisper_model": "base",
        "whisper_device": "cpu",
        "whisper_download_root": "/tmp/test_models",
        "transcription_dir": "/tmp/test_transcriptions",
        "upload_dir": "/tmp/test_uploads",
        "temp_dir": "/tmp/test_temp",
        "redis_host": "localhost",
        "redis_port": 6379,
        "redis_db": 15,
        "log_level": "DEBUG",
    }


# ============================================================================
# FIXTURES DE EVENT LOOP (para testes assíncronos)
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Cria event loop compartilhado para testes assíncronos."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# MARKERS CUSTOMIZADOS
# ============================================================================

def pytest_configure(config):
    """Registra markers customizados."""
    config.addinivalue_line("markers", "unit: marca teste como unitário")
    config.addinivalue_line("markers", "integration: marca teste como integração")
    config.addinivalue_line("markers", "e2e: marca teste como end-to-end")
    config.addinivalue_line("markers", "real: usa APIs/serviços reais")
    config.addinivalue_line("markers", "slow: testes que demoram > 5s")
    config.addinivalue_line("markers", "gpu: requer GPU")
    config.addinivalue_line("markers", "celery: requer Celery rodando")


# ============================================================================
# HOOKS DE TESTE
# ============================================================================

def pytest_collection_modifyitems(config, items):
    """Modifica items de teste antes da execução."""
    # Adiciona marker 'slow' automaticamente para testes longos
    for item in items:
        if "e2e" in item.nodeid or "real" in item.nodeid:
            item.add_marker(pytest.mark.slow)


@pytest.fixture(autouse=True)
def reset_environment_after_test():
    """Reset de ambiente após cada teste."""
    yield
    # Cleanup após teste
    import gc
    gc.collect()
