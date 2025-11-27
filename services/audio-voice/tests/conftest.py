"""
Fixtures globais para testes RVC
Sprint 5 - Unit Tests Suite
"""
import pytest
import torch
import numpy as np
from pathlib import Path
import tempfile
import soundfile as sf


@pytest.fixture(scope="session")
def sample_audio_3s():
    """
    Áudio sintético 3 segundos @ 24kHz
    
    Returns:
        Tuple[np.ndarray, int]: (audio_data, sample_rate)
    """
    sr = 24000
    duration = 3.0
    samples = int(sr * duration)
    
    # Onda senoidal com ruído
    t = np.linspace(0, duration, samples)
    audio = (np.sin(2 * np.pi * 440 * t) * 0.3 +
             np.random.randn(samples) * 0.05)
    
    return audio.astype(np.float32), sr


@pytest.fixture(scope="session")
def sample_audio_10s():
    """
    Áudio sintético 10 segundos @ 24kHz
    
    Returns:
        Tuple[np.ndarray, int]: (audio_data, sample_rate)
    """
    sr = 24000
    duration = 10.0
    samples = int(sr * duration)
    
    # Sinal mais complexo
    t = np.linspace(0, duration, samples)
    audio = (np.sin(2 * np.pi * 440 * t) * 0.3 +
             np.sin(2 * np.pi * 880 * t) * 0.2 +
             np.random.randn(samples) * 0.05)
    
    return audio.astype(np.float32), sr


@pytest.fixture(scope="session")
def sample_audio_short():
    """
    Áudio muito curto (0.5s) @ 24kHz
    
    Returns:
        Tuple[np.ndarray, int]: (audio_data, sample_rate)
    """
    sr = 24000
    duration = 0.5
    samples = int(sr * duration)
    
    t = np.linspace(0, duration, samples)
    audio = np.sin(2 * np.pi * 440 * t) * 0.3
    
    return audio.astype(np.float32), sr


@pytest.fixture
def mock_rvc_model(tmp_path):
    """
    Cria modelo RVC fake para testes
    
    Args:
        tmp_path: pytest fixture (temporary directory)
    
    Returns:
        RvcModel: Modelo RVC com arquivos fake
    """
    from app.models import RvcModel
    
    # Cria arquivo .pth fake
    model_path = tmp_path / "test_model.pth"
    torch.save({
        'weight': {'generator': {}},
        'params': {'sampling_rate': 40000}
    }, model_path)
    
    # Cria arquivo .index fake
    index_path = tmp_path / "test_model.index"
    index_path.write_text("fake index data")
    
    return RvcModel.create_new(
        name="Test Model",
        model_path=str(model_path),
        index_path=str(index_path),
        description="Model for testing"
    )


@pytest.fixture
def mock_rvc_model_no_index(tmp_path):
    """
    Modelo RVC sem arquivo .index (edge case)
    
    Args:
        tmp_path: pytest fixture
    
    Returns:
        RvcModel: Modelo sem index
    """
    from app.models import RvcModel
    
    model_path = tmp_path / "test_no_index.pth"
    torch.save({'weight': {}}, model_path)
    
    return RvcModel.create_new(
        name="No Index Model",
        model_path=str(model_path),
        index_path=None,
        description="Model without index"
    )


@pytest.fixture
def rvc_params_default():
    """
    Parâmetros RVC padrão
    
    Returns:
        RvcParameters: Params com valores default
    """
    from app.models import RvcParameters
    return RvcParameters()


@pytest.fixture
def rvc_params_extreme():
    """
    Parâmetros RVC com valores extremos (mas válidos)
    
    Returns:
        RvcParameters: Params nos limites
    """
    from app.models import RvcParameters
    return RvcParameters(
        pitch=12,  # Máximo
        index_rate=1.0,  # Máximo
        protect=0.5,  # Máximo
        rms_mix_rate=1.0,  # Máximo
        filter_radius=7,  # Máximo
        f0_method='rmvpe'
    )


@pytest.fixture
def temp_audio_file(tmp_path, sample_audio_3s):
    """
    Cria arquivo WAV temporário para testes
    
    Args:
        tmp_path: pytest fixture
        sample_audio_3s: fixture de áudio
    
    Returns:
        Path: Caminho do arquivo WAV
    """
    audio, sr = sample_audio_3s
    audio_file = tmp_path / "test_audio.wav"
    sf.write(audio_file, audio, sr)
    return audio_file


@pytest.fixture
def mock_voice_profile(tmp_path):
    """
    Cria VoiceProfile fake para testes
    
    Args:
        tmp_path: pytest fixture
    
    Returns:
        VoiceProfile: Perfil de voz fake
    """
    from app.models import VoiceProfile
    from datetime import datetime, timedelta
    
    # Cria arquivo de áudio fake
    source_audio = tmp_path / "voice_sample.wav"
    profile_path = tmp_path / "voice_profile.wav"
    
    # Áudio sintético
    sr = 24000
    duration = 5.0
    samples = int(sr * duration)
    audio = np.random.randn(samples).astype(np.float32) * 0.1
    
    sf.write(source_audio, audio, sr)
    sf.write(profile_path, audio, sr)
    
    return VoiceProfile.create_new(
        name="Test Voice",
        language="en",
        source_audio_path=str(source_audio),
        profile_path=str(profile_path),
        duration=duration,
        sample_rate=sr,
        ttl_days=30
    )


@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """
    Cleanup automático após cada teste
    
    Remove arquivos temporários criados durante testes
    """
    yield
    # Cleanup após teste (se necessário)
    # Pytest já limpa tmp_path automaticamente


# Markers personalizados
def pytest_configure(config):
    """Configura markers personalizados"""
    config.addinivalue_line(
        "markers", "slow: marca testes lentos (skip com -m 'not slow')"
    )
    config.addinivalue_line(
        "markers", "gpu: marca testes que requerem GPU"
    )
    config.addinivalue_line(
        "markers", "integration: marca testes de integração"
    )
