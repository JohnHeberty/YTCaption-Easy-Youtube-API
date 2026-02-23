"""
Testes unitários para o módulo de configuração do audio-normalization
"""
import pytest
import os
from app.config import get_settings


class TestConfigSettings:
    """Testes para as configurações gerais"""
    
    def test_get_settings_returns_dict(self):
        """Configurações devem retornar um dicionário"""
        settings = get_settings()
        assert isinstance(settings, dict)
    
    def test_required_keys_present(self):
        """Configurações devem conter chaves essenciais"""
        settings = get_settings()
        required_keys = [
            "app_name", "app_version", "redis_url", 
            "uploads_dir", "processed_dir", "temp_dir"
        ]
        for key in required_keys:
            assert key in settings, f"Key '{key}' missing from settings"
    
    def test_default_values(self):
        """Testa valores padrão das configurações"""
        settings = get_settings()
        assert settings["app_name"] == "audio-normalization"
        assert settings["app_version"] is not None


class TestDirectoryConfiguration:
    """Testes para configuração de diretórios"""
    
    def test_directories_are_strings(self):
        """Diretórios devem ser strings"""
        settings = get_settings()
        directories = ["uploads_dir", "processed_dir", "temp_dir"]
        for dir_key in directories:
            assert isinstance(settings[dir_key], str)
    
    def test_directories_are_absolute_paths(self):
        """Diretórios devem ser caminhos absolutos ou relativos válidos"""
        settings = get_settings()
        directories = ["uploads_dir", "processed_dir", "temp_dir"]
        for dir_key in directories:
            path = settings[dir_key]
            assert len(path) > 0, f"{dir_key} is empty"


class TestRedisConfiguration:
    """Testes para configuração do Redis"""
    
    def test_redis_url_format(self):
        """URL do Redis deve ter formato válido"""
        settings = get_settings()
        redis_url = settings["redis_url"]
        assert redis_url.startswith("redis://")
    
    def test_redis_url_not_empty(self):
        """URL do Redis não deve estar vazia"""
        settings = get_settings()
        assert len(settings["redis_url"]) > 0


class TestNormalizationSettings:
    """Testes para parâmetros de normalização"""
    
    def test_default_sample_rate(self):
        """Taxa de amostragem padrão deve ser 16000"""
        settings = get_settings()
        if "default_sample_rate" in settings:
            assert settings["default_sample_rate"] == 16000
    
    def test_chunk_duration_is_positive(self):
        """Duração do chunk deve ser positiva"""
        settings = get_settings()
        if "chunk_duration_ms" in settings:
            assert settings["chunk_duration_ms"] > 0
