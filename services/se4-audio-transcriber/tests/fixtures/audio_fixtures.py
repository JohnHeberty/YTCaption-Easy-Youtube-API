"""
Fixtures customizadas para áudio.
"""
import pytest
from pathlib import Path
from typing import Generator
import tempfile
import shutil


@pytest.fixture
def audio_fixtures_dir() -> Path:
    """Retorna diretório com fixtures de áudio."""
    return Path(__file__).parent.parent / "assets" / "audio_samples"


@pytest.fixture
def multi_format_audio_files(temp_dir: Path) -> dict:
    """
    Gera arquivos de áudio em múltiplos formatos para teste.
    Retorna dict com paths para diferentes formatos.
    """
    import subprocess
    
    formats = {}
    base_audio = temp_dir / "base.wav"
    
    # Gera áudio base
    cmd = [
        "ffmpeg", "-f", "lavfi", "-i",
        "sine=frequency=440:duration=2",
        "-ar", "16000", "-ac", "1", "-y", str(base_audio)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        formats["wav"] = base_audio
        
        # Converte para outros formatos
        for fmt in ["mp3", "ogg", "flac", "m4a"]:
            output = temp_dir / f"audio.{fmt}"
            cmd = ["ffmpeg", "-i", str(base_audio), "-y", str(output)]
            subprocess.run(cmd, capture_output=True, check=True)
            formats[fmt] = output
            
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("FFmpeg não disponível para gerar áudios multi-formato")
    
    return formats


@pytest.fixture
def speech_audio_file(temp_dir: Path) -> Path:
    """
    Gera arquivo de áudio com fala sintética usando espeak.
    Se espeak não estiver disponível, retorna arquivo silencioso.
    """
    audio_path = temp_dir / "speech.wav"
    
    import subprocess
    
    # Tenta usar espeak para gerar fala
    try:
        cmd = [
            "espeak", "-w", str(audio_path),
            "Hello world. This is a test."
        ]
        subprocess.run(cmd, capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        # Fallback: gera silêncio
        cmd = [
            "ffmpeg", "-f", "lavfi", "-i",
            "anullsrc=duration=3",
            "-ar", "16000", "-ac", "1", "-y", str(audio_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)
    
    return audio_path


@pytest.fixture
def noisy_audio_file(temp_dir: Path) -> Path:
    """Gera áudio com ruído para testes de robustez."""
    audio_path = temp_dir / "noisy.wav"
    
    import subprocess
    cmd = [
        "ffmpeg", "-f", "lavfi", "-i",
        "anoisesrc=d=5:c=white:r=16000:a=0.5",
        "-ar", "16000", "-ac", "1", "-y", str(audio_path)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("FFmpeg não disponível")
    
    return audio_path


@pytest.fixture
def long_audio_file(temp_dir: Path) -> Path:
    """Gera áudio longo (1 minuto) para testes de performance."""
    audio_path = temp_dir / "long.wav"
    
    import subprocess
    cmd = [
        "ffmpeg", "-f", "lavfi", "-i",
        "sine=frequency=440:duration=60",
        "-ar", "16000", "-ac", "1", "-y", str(audio_path)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("FFmpeg não disponível")
    
    return audio_path


@pytest.fixture
def stereo_audio_file(temp_dir: Path) -> Path:
    """Gera áudio estéreo para testes de conversão."""
    audio_path = temp_dir / "stereo.wav"
    
    import subprocess
    cmd = [
        "ffmpeg", "-f", "lavfi", "-i",
        "sine=frequency=440:duration=3",
        "-ar", "44100", "-ac", "2", "-y", str(audio_path)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("FFmpeg não disponível")
    
    return audio_path
