"""
Testes para o serviço de transcrição de áudio.

Estrutura de testes:
- test_validators.py: Testes de validação
- test_whisper_engine.py: Testes do engine Whisper
- test_transcription_service.py: Testes do serviço
- test_main.py: Testes de integração da API

Configuração:
- pytest.ini define marcadores e timeout
- conftest.py configura fixtures compartilhadas
"""

import pytest

# Marcadores para categorização de testes
pytest.register_assert_rewrite("app")

def pytest_configure(config):
    """Configura marcadores personalizados."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "requires_model: Tests requiring Whisper model")
