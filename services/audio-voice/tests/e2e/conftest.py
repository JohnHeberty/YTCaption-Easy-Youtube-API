"""
Pytest configuration for E2E tests
Fixtures compartilhadas entre testes E2E
"""

import pytest
import os


@pytest.fixture(scope="session")
def gpu_available():
    """Verifica se GPU está disponível"""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


@pytest.fixture(scope="session")
def device(gpu_available):
    """Retorna device a ser usado nos testes"""
    if gpu_available:
        return "cuda"
    return "cpu"


@pytest.fixture(scope="session")
def test_settings():
    """Settings para testes E2E"""
    return {
        'tts_engine_default': 'xtts',
        'tts_engines': {
            'xtts': {
                'enabled': True,
                'device': None,  # Auto-detect
                'fallback_to_cpu': True,
                'model_name': 'tts_models/multilingual/multi-dataset/xtts_v2'
            },
            'f5tts': {
                'enabled': True,
                'device': None,  # Auto-detect
                'fallback_to_cpu': True,
                'model_name': 'SWivid/F5-TTS'
            }
        },
        'whisper': {
            'model': 'base',  # Modelo rápido para testes
            'device': None,
            'compute_type': 'float32'
        }
    }


@pytest.fixture(scope="session", autouse=True)
def print_environment_info(gpu_available, device):
    """Imprime informações do ambiente de teste"""
    print("\n" + "="*80)
    print("🔧 E2E TEST ENVIRONMENT")
    print("="*80)
    print(f"Device: {device}")
    print(f"GPU Available: {gpu_available}")
    
    if gpu_available:
        import torch
        print(f"CUDA Version: {torch.version.cuda}")
        print(f"GPU Name: {torch.cuda.get_device_name(0)}")
        print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
    
    print("="*80 + "\n")
    
    yield


def pytest_configure(config):
    """Configuração customizada do pytest"""
    config.addinivalue_line(
        "markers", 
        "e2e: mark test as end-to-end test with real models"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )
