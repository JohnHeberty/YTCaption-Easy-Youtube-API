"""
Configuração de testes pytest para audio-voice service
"""
import pytest
import os
import sys
from pathlib import Path

# Adiciona diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

# Mock do Redis para testes
@pytest.fixture
def mock_redis(monkeypatch):
    """Mock do Redis para testes unitários"""
    class MockRedis:
        def __init__(self, *args, **kwargs):
            self._data = {}
        
        def set(self, key, value):
            self._data[key] = value
        
        def get(self, key):
            return self._data.get(key)
        
        def delete(self, key):
            if key in self._data:
                del self._data[key]
                return 1
            return 0
        
        def keys(self, pattern):
            import fnmatch
            return [k for k in self._data.keys() if fnmatch.fnmatch(k, pattern)]
        
        def ping(self):
            return True
        
        def flushdb(self):
            self._data.clear()
    
    monkeypatch.setattr("redis.Redis.from_url", lambda *args, **kwargs: MockRedis())
    return MockRedis()


@pytest.fixture
def mock_openvoice_client(monkeypatch):
    """Mock do OpenVoice client para testes"""
    from app.openvoice_client import OpenVoiceClient
    import numpy as np
    
    class MockClient:
        def __init__(self, *args, **kwargs):
            self.device = 'cpu'
            self._models_loaded = True
        
        async def generate_dubbing(self, *args, **kwargs):
            # Retorna áudio mock (1 segundo de silêncio em WAV)
            audio_bytes = b'RIFF' + b'\x00' * 100  # WAV simplificado
            duration = 1.0
            return audio_bytes, duration
        
        async def clone_voice(self, *args, **kwargs):
            from app.models import VoiceProfile
            return VoiceProfile.create_new(
                name="Test Voice",
                language="en",
                source_audio_path="/tmp/test.wav",
                profile_path="/tmp/test.pkl"
            )
    
    monkeypatch.setattr("app.processor.OpenVoiceClient", MockClient)
    return MockClient()


# Configurações de teste
@pytest.fixture(scope="session")
def test_settings():
    """Configurações de teste"""
    return {
        "redis_url": "redis://localhost:6379/15",  # DB separado para testes
        "upload_dir": "./test_uploads",
        "processed_dir": "./test_processed",
        "temp_dir": "./test_temp",
        "voice_profiles_dir": "./test_voice_profiles",
        "max_file_size_mb": 10,
        "max_text_length": 1000,
    }


@pytest.fixture(autouse=True)
def cleanup_test_dirs():
    """Limpa diretórios de teste antes e depois de cada teste"""
    import shutil
    test_dirs = [
        "./test_uploads",
        "./test_processed",
        "./test_temp",
        "./test_voice_profiles"
    ]
    
    # Cleanup antes
    for dir_path in test_dirs:
        if Path(dir_path).exists():
            shutil.rmtree(dir_path)
        Path(dir_path).mkdir(exist_ok=True, parents=True)
    
    yield
    
    # Cleanup depois
    for dir_path in test_dirs:
        if Path(dir_path).exists():
            shutil.rmtree(dir_path)
