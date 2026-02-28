"""
Fixtures específicas para testes de resiliência.
"""
import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture(scope="module")
def test_audio_real() -> Path:
    """
    Retorna caminho para o arquivo de teste REAL (TEST-.ogg).
    
    Este é um arquivo de áudio válido usado para validação end-to-end.
    Tamanho: ~75KB
    """
    audio_path = Path(__file__).parent.parent / "TEST-.ogg"
    assert audio_path.exists(), f"Arquivo TEST-.ogg não encontrado em {audio_path}"
    assert audio_path.stat().st_size > 0, "Arquivo TEST-.ogg está vazio"
    return audio_path


@pytest.fixture(scope="function")
def corrupted_audio_file(tmp_path: Path) -> Path:
    """
    Cria arquivo de áudio corrompido para testar error handling.
    """
    corrupted = tmp_path / "corrupted.ogg"
    # Cria arquivo com conteúdo inválido
    corrupted.write_bytes(b"NOT_A_VALID_AUDIO_FILE" * 100)
    return corrupted


@pytest.fixture(scope="function")
def empty_audio_file(tmp_path: Path) -> Path:
    """
    Cria arquivo de áudio vazio para testar edge cases.
    """
    empty = tmp_path / "empty.ogg"
    empty.touch()
    return empty


@pytest.fixture(scope="function")
def large_dummy_file(tmp_path: Path) -> Path:
    """
    Cria arquivo grande (10MB) para testar limites de memória.
    """
    large = tmp_path / "large.bin"
    # Cria arquivo de 10MB
    large.write_bytes(b"\x00" * (10 * 1024 * 1024))
    return large


@pytest.fixture(scope="function")
def temp_work_dir(tmp_path: Path) -> Path:
    """
    Diretório temporário de trabalho para cada teste.
    """
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir
