"""
Configuração global de fixtures para pytest.
Implementa geradores de vídeo e áudio sintéticos SEM MOCKS.
"""
import os
import sys
import shutil
import tempfile
from pathlib import Path
from typing import Generator, Dict
import pytest
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

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
    yield
    # Cleanup após todos os testes
    print("\n✅ Ambiente de teste finalizado")


# ============================================================================
# FIXTURES DE DIRETÓRIOS TEMPORÁRIOS
# ============================================================================

@pytest.fixture(scope="function")
def temp_dir() -> Generator[Path, None, None]:
    """Cria diretório temporário para cada teste."""
    tmp = tempfile.mkdtemp(prefix="test_ytcaption_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="function")
def test_dirs(temp_dir: Path) -> Dict[str, Path]:
    """Cria estrutura de diretórios para testes de pipeline."""
    dirs = {
        "transform": temp_dir / "transform" / "videos",
        "validate": temp_dir / "validate",
        "approved": temp_dir / "approved" / "videos",
        "rejected": temp_dir / "rejected" / "videos",
        "output": temp_dir / "output",
    }
    for dir_path in dirs.values():
        dir_path.mkdir(parents=True, exist_ok=True)
    return dirs


# ============================================================================
# FIXTURES DE VÍDEO SINTÉTICO (SEM MOCKS)
# ============================================================================

@pytest.fixture(scope="session")
def sample_video_path(tmp_path_factory) -> Path:
    """
    Gera vídeo real de teste com legendas visíveis usando FFmpeg.
    Vídeo de 5 segundos, 1280x720, com legendas hardcoded.
    """
    video_dir = tmp_path_factory.mktemp("videos")
    video_path = video_dir / "test_video_with_subs.mp4"
    
    # Gera vídeo com FFmpeg (desenha legendas diretamente)
    cmd = [
        "ffmpeg", "-f", "lavfi", "-i", 
        "color=c=blue:s=1280x720:d=5:r=30",
        "-vf", 
        "drawtext=text='Test Subtitle Line 1':fontsize=40:fontcolor=white:"
        "x=(w-text_w)/2:y=h-100:box=1:boxcolor=black@0.5:boxborderw=5,"
        "drawtext=text='Test Subtitle Line 2':fontsize=40:fontcolor=white:"
        "x=(w-text_w)/2:y=h-50:box=1:boxcolor=black@0.5:boxborderw=5",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y",
        str(video_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg falhou: {result.stderr}")
    
    assert video_path.exists(), "Vídeo não foi criado"
    assert video_path.stat().st_size > 0, "Vídeo está vazio"
    
    return video_path


@pytest.fixture(scope="session")
def sample_video_no_subs(tmp_path_factory) -> Path:
    """Gera vídeo real SEM legendas para testes de detecção negativa."""
    video_dir = tmp_path_factory.mktemp("videos")
    video_path = video_dir / "no_subs.mp4"
    
    cmd = [
        "ffmpeg", "-f", "lavfi", "-i",
        "color=c=green:s=1280x720:d=3:r=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y",
        str(video_path)
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    return video_path


@pytest.fixture(scope="session")
def video_with_subtitles(tmp_path_factory) -> Path:
    """Gera vídeo real COM legendas queimadas para testes de detecção positiva."""
    video_dir = tmp_path_factory.mktemp("videos")
    video_path = video_dir / "test_video_with_subs.mp4"
    
    # Cria vídeo com legendas queimadas usando drawtext do FFmpeg
    cmd = [
        "ffmpeg", "-f", "lavfi", "-i",
        "color=c=blue:s=1280x720:d=3:r=30",
        "-vf", "drawtext=text='This is a test subtitle':fontsize=40:fontcolor=white:x=(w-text_w)/2:y=h-100:box=1:boxcolor=black@0.8:boxborderw=10",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y",
        str(video_path)
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    return video_path


@pytest.fixture(scope="function")
def video_with_metadata(temp_dir: Path) -> Path:
    """Cria vídeo com metadados específicos para testes."""
    video_path = temp_dir / "metadata_test.mp4"
    
    cmd = [
        "ffmpeg", "-f", "lavfi", "-i",
        "testsrc=duration=2:size=640x480:rate=30",
        "-metadata", "title=Test Video",
        "-metadata", "comment=Generated by pytest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y",
        str(video_path)
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    return video_path


# ============================================================================
# FIXTURES DE ÁUDIO REAL (SEM MOCKS)
# ============================================================================

@pytest.fixture(scope="session")
def sample_audio_path(tmp_path_factory) -> Path:
    """Gera arquivo de áudio real com tom de 440Hz (Lá padrão)."""
    audio_dir = tmp_path_factory.mktemp("audio")
    audio_path = audio_dir / "test_audio.ogg"
    
    cmd = [
        "ffmpeg", "-f", "lavfi", "-i",
        "sine=frequency=440:duration=3",
        "-c:a", "libopus", "-y",
        str(audio_path)
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    assert audio_path.exists()
    return audio_path


@pytest.fixture(scope="function")
def silent_audio(temp_dir: Path) -> Path:
    """Gera áudio silencioso para testes de VAD."""
    audio_path = temp_dir / "silent.ogg"
    
    cmd = [
        "ffmpeg", "-f", "lavfi", "-i",
        "anullsrc=r=16000:cl=mono:d=2",
        "-c:a", "libopus", "-y",
        str(audio_path)
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    return audio_path


@pytest.fixture(scope="function")
def noisy_audio(temp_dir: Path) -> Path:
    """Gera áudio com ruído branco para testes."""
    audio_path = temp_dir / "noisy.ogg"
    
    cmd = [
        "ffmpeg", "-f", "lavfi", "-i",
        "anoisesrc=d=2:c=white:r=16000:a=0.5",
        "-c:a", "libopus", "-y",
        str(audio_path)
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    return audio_path


# ============================================================================
# FIXTURES DE IMAGENS (FRAMES DE VÍDEO)
# ============================================================================

@pytest.fixture(scope="function")
def frame_with_subtitle(temp_dir: Path) -> Path:
    """Gera frame PNG com legenda desenhada usando Pillow."""
    frame_path = temp_dir / "frame_with_sub.png"
    
    # Cria imagem com Pillow
    img = Image.new('RGB', (1280, 720), color='blue')
    draw = ImageDraw.Draw(img)
    
    # Tenta carregar fonte, se falhar usa fonte padrão
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except:
        font = ImageFont.load_default()
    
    # Desenha retângulo preto (fundo da legenda)
    draw.rectangle([(100, 620), (1180, 700)], fill='black')
    # Desenha texto
    draw.text((640, 650), "This is a test subtitle", fill='white', anchor='mm', font=font)
    
    img.save(frame_path)
    return frame_path


@pytest.fixture(scope="function")
def frame_no_subtitle(temp_dir: Path) -> Path:
    """Gera frame sem legendas."""
    frame_path = temp_dir / "frame_no_sub.png"
    img = Image.new('RGB', (1280, 720), color='green')
    img.save(frame_path)
    return frame_path


# ============================================================================
# FIXTURES DE ARQUIVOS ASS
# ============================================================================

@pytest.fixture(scope="function")
def sample_ass_file(temp_dir: Path) -> Path:
    """Cria arquivo .ass válido para testes."""
    ass_path = temp_dir / "test_subs.ass"
    content = """[Script Info]
Title: Test Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000088EF,&H00000000,&H00666666,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Line 1 of subtitle
Dialogue: 0,0:00:03.50,0:00:05.00,Default,,0,0,0,,Line 2 of subtitle
"""
    ass_path.write_text(content)
    return ass_path


# ============================================================================
# FIXTURES DE CONFIGURAÇÃO
# ============================================================================

@pytest.fixture(scope="function")
def test_settings(test_dirs: Dict[str, Path]) -> Dict:
    """Retorna configurações de teste completas."""
    return {
        "transform_dir": str(test_dirs["transform"]),
        "validate_dir": str(test_dirs["validate"]),
        "approved_dir": str(test_dirs["approved"]),
        "rejected_dir": str(test_dirs["rejected"]),
        "output_dir": str(test_dirs["output"]),
        "redis_db": 15,
        "redis_host": "localhost",
        "redis_port": 6379,
        "subtitle_detection_threshold": 0.7,
        "max_retries": 3,
        "ffmpeg_timeout": 30,
    }


# ============================================================================
# FIXTURES DE REDIS (REAL - SEM MOCKS)
# ============================================================================

@pytest.fixture(scope="function")
def redis_client():
    """Retorna cliente Redis real conectado ao DB 15 (para testes)."""
    try:
        import redis
        client = redis.Redis(host='localhost', port=6379, db=15, decode_responses=True)
        client.ping()
        
        # Limpa DB antes do teste
        client.flushdb()
        
        yield client
        
        # Limpa DB após o teste
        client.flushdb()
        client.close()
    except Exception as e:
        pytest.skip(f"Redis não disponível: {e}")


@pytest.fixture(scope="function")
def test_redis_url():
    """Retorna URL Redis para testes de integração."""
    return "redis://localhost:6379/15"


# ============================================================================
# FIXTURES DE VALIDAÇÃO
# ============================================================================

@pytest.fixture(scope="function")
def assert_video_valid():
    """Helper para validar vídeos gerados."""
    def _validate(video_path: Path):
        assert video_path.exists(), f"Vídeo não existe: {video_path}"
        assert video_path.stat().st_size > 0, "Vídeo está vazio"
        
        # Valida com FFprobe
        cmd = ["ffprobe", "-v", "error", "-show_format", "-show_streams", str(video_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"Vídeo inválido: {result.stderr}"
        
        return True
    return _validate


@pytest.fixture(scope="function")
def assert_audio_valid():
    """Helper para validar áudios gerados."""
    def _validate(audio_path: Path):
        assert audio_path.exists(), f"Áudio não existe: {audio_path}"
        assert audio_path.stat().st_size > 0, "Áudio está vazio"
        
        # Valida com FFprobe
        cmd = ["ffprobe", "-v", "error", "-show_format", str(audio_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"Áudio inválido: {result.stderr}"
        
        return True
    return _validate


# ============================================================================
# ALIASES DE FIXTURES (para compatibilidade com sprints)
# ============================================================================

@pytest.fixture(scope="session")
def real_test_video(sample_video_path: Path) -> Path:
    """Alias para sample_video_path (usado em sprints)."""
    return sample_video_path


@pytest.fixture(scope="session")
def real_test_audio(sample_audio_path: Path) -> Path:
    """Alias para sample_audio_path (usado em sprints)."""
    return sample_audio_path


# ============================================================================
# MARKERS PERSONALIZADOS
# ============================================================================

def pytest_configure(config):
    """Registra markers customizados."""
    config.addinivalue_line("markers", "unit: marca teste como unitário")
    config.addinivalue_line("markers", "integration: marca teste como integração")
    config.addinivalue_line("markers", "e2e: marca teste end-to-end")
    config.addinivalue_line("markers", "slow: marca testes lentos (>5s)")
    config.addinivalue_line("markers", "requires_video: requer vídeo real")
    config.addinivalue_line("markers", "requires_audio: requer áudio real")
    config.addinivalue_line("markers", "requires_redis: requer Redis ativo")
    config.addinivalue_line("markers", "requires_ffmpeg: requer FFmpeg/FFprobe")
