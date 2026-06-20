"""
Testes Unitários - Config Module
Princípio SOLID: Single Responsibility - Testa apenas configurações
"""
import pytest
from app.core.config import get_settings, get_supported_languages, is_language_supported, get_whisper_models


class TestConfigSettings:
    """Testa carregamento e validação de configurações"""

    def test_get_settings_returns_instance(self):
        """Deve retornar instância Pydantic com configurações"""
        settings = get_settings()
        assert hasattr(settings, 'whisper_model')

    def test_settings_has_required_fields(self):
        """Deve conter todos campos obrigatórios"""
        settings = get_settings()
        assert settings.whisper_model is not None
        assert settings.whisper_device is not None
        assert settings.upload_dir is not None
        assert settings.log_level is not None

    def test_settings_default_values(self):
        """Deve ter valores padrão corretos"""
        settings = get_settings()
        assert settings.whisper_model in ['tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3']
        assert settings.whisper_device in ['cpu', 'cuda']
        assert settings.log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']


class TestLanguageSupport:
    """Testa validação de linguagens suportadas"""

    def test_get_supported_languages_returns_list(self):
        """Deve retornar lista de linguagens"""
        languages = get_supported_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0

    def test_supported_languages_contains_auto(self):
        """Deve conter 'auto' para detecção automática"""
        languages = get_supported_languages()
        assert 'auto' in languages

    def test_supported_languages_contains_common_languages(self):
        """Deve conter idiomas comuns"""
        languages = get_supported_languages()
        common_languages = ['en', 'pt', 'es', 'fr', 'de', 'zh', 'ja']
        for lang in common_languages:
            assert lang in languages, f"Idioma '{lang}' não encontrado"

    def test_is_language_supported_valid_language(self):
        """Deve validar linguagens válidas"""
        assert is_language_supported('en') is True
        assert is_language_supported('pt') is True
        assert is_language_supported('auto') is True

    def test_is_language_supported_invalid_language(self):
        """Deve rejeitar linguagens inválidas"""
        assert is_language_supported('xyz') is False
        assert is_language_supported('invalid') is False
        assert is_language_supported('') is False
        assert is_language_supported(None) is False

    def test_is_language_supported_case_sensitive(self):
        """Deve ser case-sensitive"""
        assert is_language_supported('EN') is False
        assert is_language_supported('en') is True


class TestWhisperModels:
    """Testa validação de modelos Whisper"""

    def test_get_whisper_models_returns_list(self):
        """Deve retornar lista de modelos"""
        models = get_whisper_models()
        assert isinstance(models, list)
        assert len(models) > 0

    def test_whisper_models_contains_all_sizes(self):
        """Deve conter todos tamanhos de modelo"""
        models = get_whisper_models()
        expected_models = ['tiny', 'base', 'small', 'medium', 'large']
        for model in expected_models:
            assert model in models, f"Modelo '{model}' não encontrado"

    def test_whisper_models_no_duplicates(self):
        """Não deve ter modelos duplicados"""
        models = get_whisper_models()
        assert len(models) == len(set(models))


class TestConfigIntegrity:
    """Testa integridade e consistência das configurações"""

    def test_directories_are_strings(self):
        """Diretórios devem ser caminhos válidos"""
        settings = get_settings()
        assert isinstance(settings.upload_dir, str)
        assert len(settings.upload_dir) > 0
        assert isinstance(settings.transcription_dir, str)
        assert isinstance(settings.log_dir, str)

    def test_chunk_settings_are_valid(self):
        """Configurações de chunking devem ser válidas"""
        settings = get_settings()
        assert isinstance(settings.enable_chunking, bool)
        assert settings.chunk_length_seconds > 0
        assert settings.chunk_overlap_seconds >= 0

    def test_cache_ttl_is_positive(self):
        """TTL de cache deve ser positivo"""
        settings = get_settings()
        assert settings.cache_ttl_hours > 0
