"""
Testes unitários para config.py
"""
import pytest
from app.config import (
    get_settings,
    get_supported_languages,
    is_language_supported,
    get_voice_presets,
    is_voice_preset_valid
)


class TestConfig:
    """Testes para configurações"""
    
    def test_get_settings(self):
        """Testa carregamento de settings"""
        settings = get_settings()
        
        assert settings is not None
        assert 'app_name' in settings
        assert 'redis_url' in settings
        assert 'openvoice' in settings
    
    def test_get_supported_languages(self):
        """Testa listagem de idiomas"""
        languages = get_supported_languages()
        
        assert isinstance(languages, list)
        assert len(languages) > 0
        assert 'en' in languages
        assert 'pt' in languages
    
    def test_is_language_supported(self):
        """Testa validação de idiomas"""
        assert is_language_supported('en') is True
        assert is_language_supported('en-US') is True
        assert is_language_supported('pt-BR') is True
        assert is_language_supported('xyz') is False
    
    def test_get_voice_presets(self):
        """Testa listagem de vozes genéricas"""
        presets = get_voice_presets()
        
        assert isinstance(presets, dict)
        assert 'female_generic' in presets
        assert 'male_generic' in presets
    
    def test_is_voice_preset_valid(self):
        """Testa validação de preset"""
        assert is_voice_preset_valid('female_generic') is True
        assert is_voice_preset_valid('male_generic') is True
        assert is_voice_preset_valid('invalid_preset') is False
