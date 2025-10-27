"""
Configurações e fixtures compartilhadas para testes
"""
import pytest
import sys
from pathlib import Path

# Adiciona diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def test_data_dir():
    """Diretório para dados de teste"""
    data_dir = Path(__file__).parent / "test_data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


@pytest.fixture(autouse=True)
def cleanup_test_files():
    """Limpa arquivos de teste após cada teste"""
    yield
    # Cleanup após teste
    test_files = ["test_audio.mp3", "test_video.mp4", "test_output.srt"]
    for file in test_files:
        if Path(file).exists():
            Path(file).unlink()
