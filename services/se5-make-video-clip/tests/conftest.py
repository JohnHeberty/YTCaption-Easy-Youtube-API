"""
Configuração pytest para Make-Video Service.
"""

import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock

from common.test_utils.mock_redis import MockRedis
from common.test_utils.mock_celery import mock_celery_app

# Adicionar app ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

import pytest


# ============================================================================
# FIXTURES DE INFRAESTRUTURA (existentes)
# ============================================================================

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


# ============================================================================
# FIXTURES DE INFRAESTRUTURA (novas)
# ============================================================================

@pytest.fixture
def temp_dir():
    """Diretório temporário para testes. Equivalente a tmp_path."""
    path = Path(tempfile.mkdtemp(prefix="se5_test_"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def test_dirs(temp_dir):
    """Dict com estrutura de diretórios de pipeline."""
    dirs = {}
    for name in ("transform", "validate", "approved", "rejected", "output"):
        d = temp_dir / name
        d.mkdir(parents=True, exist_ok=True)
        dirs[name] = d
    return dirs


@pytest.fixture
def test_redis_url():
    """URL de conexão Redis para testes de integração."""
    try:
        from app.core.config import get_settings
        settings = get_settings()
        url = settings.redis_url
        import redis
        r = redis.from_url(url, decode_responses=True)
        r.ping()
        r.close()
        return url
    except Exception:
        pytest.skip("Redis não disponível")


@pytest.fixture
def redis_client(test_redis_url):
    """Cliente Redis conectado para testes de integração."""
    import redis
    return redis.from_url(test_redis_url, decode_responses=True)


# ============================================================================
# FIXTURES DE MÍDIA (session-scoped, geradas via ffmpeg)
# ============================================================================

def _generate_test_video(path: Path, duration: int = 5, color: str = "blue",
                         with_audio: bool = True, subtitle_text: str = "",
                         width: int = 1280, height: int = 720):
    """Gera vídeo de teste via ffmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={color}:s={width}x{height}:d={duration}:r=30",
    ]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
    
    if subtitle_text:
        cmd += ["-vf", f"drawtext=text='{subtitle_text}':fontsize=36:fontcolor=white:x=(w-tw)/2:y=h-60"]
    
    cmd += ["-c:v", "libx264", "-c:a", "aac", "-shortest", str(path)]
    
    subprocess.run(cmd, capture_output=True, check=True)


def _generate_test_audio(path: Path, duration: int = 3, source: str = "sine"):
    """Gera áudio de teste via ffmpeg."""
    if source == "sine":
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
            "-c:a", "libvorbis", str(path),
        ]
    elif source == "silent":
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", str(duration),
            "-c:a", "libvorbis", str(path),
        ]
    elif source == "noise":
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anoisesrc=d={duration}:c=pink:a=0.5",
            "-c:a", "libvorbis", str(path),
        ]
    else:
        raise ValueError(f"Unknown source: {source}")
    
    subprocess.run(cmd, capture_output=True, check=True)


@pytest.fixture(scope="session")
def real_test_video(tmp_path_factory):
    """Vídeo real de teste (5s, 640x480, com áudio)."""
    path = tmp_path_factory.mktemp("media") / "test_video.mp4"
    _generate_test_video(path, duration=5, color="blue", with_audio=True)
    return path


@pytest.fixture(scope="session")
def real_test_audio(tmp_path_factory):
    """Áudio real de teste (3s, tom 440Hz)."""
    path = tmp_path_factory.mktemp("media") / "test_audio.ogg"
    _generate_test_audio(path, duration=3, source="sine")
    return path


@pytest.fixture(scope="session")
def sample_video_path(tmp_path_factory):
    """Vídeo de teste para OCR/detector (5s, sem legendas hardcoded)."""
    path = tmp_path_factory.mktemp("media") / "sample_video.mp4"
    _generate_test_video(path, duration=5, color="green", with_audio=True)
    return path


@pytest.fixture(scope="session")
def sample_video_no_subs(tmp_path_factory):
    """Vídeo sem legendas (5s, cor azul)."""
    path = tmp_path_factory.mktemp("media") / "sample_no_subs.mp4"
    _generate_test_video(path, duration=5, color="black", with_audio=False)
    return path


@pytest.fixture(scope="session")
def video_with_subtitles(tmp_path_factory):
    """Vídeo com legendas hardcoded via subtitles filter (5s, texto visível)."""
    tmp_dir = tmp_path_factory.mktemp("media")
    video_path = tmp_dir / "video_with_subs.mp4"
    srt_path = tmp_dir / "subs.srt"

    # Create SRT subtitle file
    srt_path.write_text(
        "1\n00:00:00,000 --> 00:00:05,000\nTest Subtitle\n\n",
        encoding="utf-8",
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=red:s=1280x720:d=5:r=30",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-vf", f"subtitles={srt_path}",
        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(video_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return video_path


@pytest.fixture(scope="session")
def silent_audio(tmp_path_factory):
    """Áudio silencioso (3s)."""
    path = tmp_path_factory.mktemp("media") / "silent.ogg"
    _generate_test_audio(path, duration=3, source="silent")
    return path


@pytest.fixture(scope="session")
def sample_audio_path(tmp_path_factory):
    """Áudio de teste (3s, tom 440Hz). Mesmo que real_test_audio."""
    path = tmp_path_factory.mktemp("media") / "sample_audio.ogg"
    _generate_test_audio(path, duration=3, source="sine")
    return path


@pytest.fixture(scope="session")
def noisy_audio(tmp_path_factory):
    """Áudio com ruído rosa (3s)."""
    path = tmp_path_factory.mktemp("media") / "noisy.ogg"
    _generate_test_audio(path, duration=3, source="noise")
    return path


@pytest.fixture(scope="session")
def sample_ass_file(tmp_path_factory):
    """Arquivo ASS de legendas de teste."""
    path = tmp_path_factory.mktemp("media") / "test_subtitles.ass"
    content = """[Script Info]
Title: Test Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,Hello World
"""
    path.write_text(content)
    return path


# ============================================================================
# MARKERS
# ============================================================================

def pytest_configure(config):
    """Configura markers personalizados."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "requires_video: requires test video files")
    config.addinivalue_line("markers", "requires_ffmpeg: requires ffmpeg installed")
    config.addinivalue_line("markers", "requires_audio: requires test audio files")
    config.addinivalue_line("markers", "requires_redis: requires Redis connection")
    config.addinivalue_line("markers", "requires_drawtext: requires ffmpeg drawtext filter")
    config.addinivalue_line("markers", "requires_paddleocr: requires PaddleOCR")
    config.addinivalue_line("markers", "critical: critical tests")
    config.addinivalue_line("markers", "e2e: end-to-end tests")
    config.addinivalue_line("markers", "external: tests needing external services")
    config.addinivalue_line("markers", "subtitle_sync: subtitle sync tests")
