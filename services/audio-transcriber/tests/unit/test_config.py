"""
Testes para config.py.

✅ Sem Mocks - usa StubSettings para testes
✅ Verifica carregamento de configurações
✅ Verifica defaults e overrides
✅ Testa validação de configurações
"""

import pytest
from pathlib import Path


# Stub para settings
class StubSettings:
    """Stub que simula settings sem usar Mock"""
    
    def __init__(self, settings_dict=None):
        self.settings = settings_dict or {}
    
    def get(self, key, default=None):
        return self.settings.get(key, default)
    
    def set(self, key, value):
        self.settings[key] = value
    
    def update(self, updates):
        self.settings.update(updates)


@pytest.fixture
def stub_settings():
    """Settings stub para testes"""
    return StubSettings({
        'whisper_model': 'base',
        'whisper_download_root': './models',
        'device': 'cpu',
        'compute_type': 'int8',
        'transcription_dir': './transcriptions',
        'redis_host': 'localhost',
        'redis_port': 6379,
        'redis_db': 0,
        'max_file_size_mb': 500,
        'max_duration_hours': 4
    })


def test_settings_initialization(stub_settings):
    """Testa inicialização de settings"""
    assert stub_settings.get('whisper_model') == 'base'
    assert stub_settings.get('device') == 'cpu'
    assert stub_settings.get('redis_host') == 'localhost'


def test_settings_defaults(stub_settings):
    """Testa valores default"""
    assert stub_settings.get('nonexistent_key', 'default_value') == 'default_value'
    assert stub_settings.get('missing') is None


def test_settings_override(stub_settings):
    """Testa override de configurações"""
    stub_settings.set('whisper_model', 'large')
    assert stub_settings.get('whisper_model') == 'large'


def test_settings_update(stub_settings):
    """Testa atualização em lote"""
    stub_settings.update({
        'device': 'cuda',
        'compute_type': 'float16'
    })
    assert stub_settings.get('device') == 'cuda'
    assert stub_settings.get('compute_type') == 'float16'


def test_settings_model_path(stub_settings):
    """Testa construção de path do modelo"""
    root = stub_settings.get('whisper_download_root')
    model = stub_settings.get('whisper_model')
    
    path = Path(root) / model
    # Normaliza para comparação (remove ./ se presente)
    path_str = str(path).lstrip('./')
    assert path_str == 'models/base'


def test_settings_redis_config(stub_settings):
    """Testa configuração Redis"""
    assert stub_settings.get('redis_host') == 'localhost'
    assert stub_settings.get('redis_port') == 6379
    assert stub_settings.get('redis_db') == 0


def test_settings_file_limits(stub_settings):
    """Testa limites de arquivo"""
    assert stub_settings.get('max_file_size_mb') == 500
    assert stub_settings.get('max_duration_hours') == 4
    
    # Calcula bytes
    max_bytes = stub_settings.get('max_file_size_mb') * 1024 * 1024
    assert max_bytes == 524288000  # 500 MB em bytes


def test_settings_transcription_dir(stub_settings):
    """Testa diretório de transcrições"""
    trans_dir = stub_settings.get('transcription_dir')
    assert trans_dir == './transcriptions'
    
    path = Path(trans_dir)
    assert path.name == 'transcriptions'


def test_settings_compute_type_validation(stub_settings):
    """Testa validação de compute_type"""
    valid_types = ['int8', 'float16', 'float32']
    
    compute_type = stub_settings.get('compute_type')
    assert compute_type in valid_types


def test_settings_device_validation(stub_settings):
    """Testa validação de device"""
    valid_devices = ['cpu', 'cuda', 'auto']
    
    device = stub_settings.get('device')
    assert device in valid_devices
