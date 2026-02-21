"""
Testes Unitários - Config Module
Princípio SOLID: Single Responsibility - Testa apenas configurações
"""
import pytest
from app.config import get_settings, get_supported_languages, is_language_supported, get_whisper_models


class TestConfigSettings:
    """Testa carregamento e validação de configurações"""
    
    def test_get_settings_returns_dict(self):
        """Deve retornar dicionário com configurações"""
        settings = get_settings()
        assert isinstance(settings, dict)
        assert 'whisper_model' in settings
        assert 'log_level' in settings
    
    def test_settings_has_required_keys(self):
        """Deve conter todas chaves obrigatórias"""
        settings = get_settings()
        required_keys = [
            'whisper_model', 'whisper_device', 'whisper_download_root',
            'upload_dir', 'transcription_dir', 'temp_dir', 'log_level'
        ]
        for key in required_keys:
            assert key in settings, f"Chave '{key}' não encontrada"
    
    def test_settings_default_values(self):
        """Deve ter valores padrão corretos"""
        settings = get_settings()
        assert settings['whisper_model'] in ['tiny', 'base', 'small', 'medium', 'large']
        assert settings['whisper_device'] in ['cpu', 'cuda']
        assert settings['log_level'] in ['DEBUG', 'INFO', 'WARNING', 'ERROR']


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
        assert is_language_supported('EN') is False  # Deve ser minúsculo
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
    
    def test_directories_are_absolute_or_relative(self):
        """Diretórios devem ser caminhos válidos"""
        settings = get_settings()
        dir_keys = ['upload_dir', 'transcription_dir', 'temp_dir', 'whisper_download_root']
        for key in dir_keys:
            directory = settings[key]
            assert isinstance(directory, str)
            assert len(directory) > 0
    
    def test_chunk_settings_are_valid(self):
        """Configurações de chunking devem ser válidas"""
        settings = get_settings()
        if 'enable_chunking' in settings:
            assert isinstance(settings['enable_chunking'], bool)
        if 'chunk_length_seconds' in settings:
            assert settings['chunk_length_seconds'] > 0
        if 'chunk_overlap_seconds' in settings:
            assert settings['chunk_overlap_seconds'] >= 0
    
    def test_cache_ttl_is_positive(self):
        """TTL de cache deve ser positivo"""
        settings = get_settings()
        if 'cache_ttl_hours' in settings:
            assert settings['cache_ttl_hours'] > 0
