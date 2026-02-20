"""
Teste de validação do Sprint 0 - Setup
Valida que todas as fixtures e configurações estão funcionando.
"""
import pytest
from pathlib import Path


@pytest.mark.unit
def test_temp_dir_fixture(temp_dir):
    """Valida que temp_dir cria diretório temporário."""
    assert temp_dir.exists()
    assert temp_dir.is_dir()
    # Testa escrita
    test_file = temp_dir / "test.txt"
    test_file.write_text("test")
    assert test_file.exists()


@pytest.mark.unit
def test_test_dirs_fixture(test_dirs):
    """Valida que test_dirs cria toda estrutura necessária."""
    required_dirs = ["transform", "validate", "approved", "rejected", "output"]
    for dir_name in required_dirs:
        assert dir_name in test_dirs
        assert test_dirs[dir_name].exists()
        assert test_dirs[dir_name].is_dir()


@pytest.mark.requires_ffmpeg
@pytest.mark.requires_video
@pytest.mark.slow
def test_sample_video_generation(sample_video_path, assert_video_valid):
    """Valida que vídeo sintético é gerado corretamente."""
    assert sample_video_path.exists()
    assert sample_video_path.suffix == ".mp4"
    assert sample_video_path.stat().st_size > 0
    
    # Valida com FFprobe
    assert_video_valid(sample_video_path)


@pytest.mark.requires_ffmpeg
@pytest.mark.requires_audio
def test_sample_audio_generation(sample_audio_path, assert_audio_valid):
    """Valida que áudio sintético é gerado corretamente."""
    assert sample_audio_path.exists()
    assert sample_audio_path.suffix == ".ogg"
    assert sample_audio_path.stat().st_size > 0
    
    # Valida com FFprobe
    assert_audio_valid(sample_audio_path)


@pytest.mark.unit
def test_frame_with_subtitle_generation(frame_with_subtitle):
    """Valida que frame com legenda é gerado."""
    assert frame_with_subtitle.exists()
    assert frame_with_subtitle.suffix == ".png"
    assert frame_with_subtitle.stat().st_size > 0


@pytest.mark.unit
def test_sample_ass_file_generation(sample_ass_file):
    """Valida que arquivo ASS é gerado corretamente."""
    assert sample_ass_file.exists()
    assert sample_ass_file.suffix == ".ass"
    
    content = sample_ass_file.read_text()
    assert "[Script Info]" in content
    assert "[Events]" in content
    assert "Dialogue:" in content


@pytest.mark.unit
def test_test_settings_fixture(test_settings, test_dirs):
    """Valida que test_settings retorna configuração completa."""
    required_keys = [
        "transform_dir",
        "validate_dir",
        "approved_dir",
        "rejected_dir",
        "output_dir",
        "redis_db",
    ]
    
    for key in required_keys:
        assert key in test_settings
        if "_dir" in key:
            assert Path(test_settings[key]).exists()


@pytest.mark.requires_redis
def test_redis_client_fixture(redis_client):
    """Valida que Redis está acessível e limpo."""
    # Testa ping
    assert redis_client.ping()
    
    # Testa operações básicas
    redis_client.set("test_key", "test_value")
    assert redis_client.get("test_key") == "test_value"
    
    # Confirma que estamos no DB correto
    info = redis_client.info("keyspace")
    # DB será limpo automaticamente pelo fixture


@pytest.mark.requires_ffmpeg
def test_ffmpeg_available():
    """Valida que FFmpeg está instalado."""
    import subprocess
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True)
    assert result.returncode == 0
    assert b"ffmpeg version" in result.stdout


@pytest.mark.requires_ffmpeg
def test_ffprobe_available():
    """Valida que FFprobe está instalado."""
    import subprocess
    result = subprocess.run(["ffprobe", "-version"], capture_output=True)
    assert result.returncode == 0
    assert b"ffprobe version" in result.stdout


@pytest.mark.unit
def test_pytest_markers_registered(pytestconfig):
    """Valida que todos os markers estão registrados."""
    markers_raw = pytestconfig.getini("markers")
    # Handle both string and marker objects
    markers = [m if isinstance(m, str) else m.name for m in markers_raw]
    # Extract just the marker name from "name: description" format
    markers = [m.split(":")[0].strip() for m in markers]
    
    expected_markers = [
        "unit",
        "integration",
        "e2e",
        "slow",
        "critical",
        "requires_video",
        "requires_audio",
        "requires_redis",
        "requires_ffmpeg",
    ]
    
    for marker in expected_markers:
        assert marker in markers, f"Marker '{marker}' não está registrado"


@pytest.mark.unit
def test_app_module_importable():
    """Valida que módulo app é importável."""
    try:
        import app
        assert app is not None
    except ImportError as e:
        pytest.fail(f"Não foi possível importar app: {e}")
