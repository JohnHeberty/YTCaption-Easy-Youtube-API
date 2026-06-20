"""
Testes unitários para o módulo de configuração do audio-normalization
"""
import pytest
import os
from app.core.config import get_settings


class TestConfigSettings:
    """Testes para as configurações gerais"""

    def test_get_settings_returns_instance(self):
        """Configurações devem retornar instância Pydantic"""
        settings = get_settings()
        assert hasattr(settings, 'app_name')

    def test_required_fields_present(self):
        """Configurações devem conter campos essenciais"""
        settings = get_settings()
        assert settings.app_name is not None
        assert settings.app_version is not None
        assert settings.redis_url is not None

    def test_default_values(self):
        """Testa valores padrão das configurações"""
        settings = get_settings()
        assert settings.app_name == "Audio Normalization Service"
        assert settings.app_version is not None


class TestDirectoryConfiguration:
    """Testes para configuração de diretórios"""

    def test_directories_are_strings(self):
        """Diretórios devem ser strings"""
        settings = get_settings()
        assert isinstance(settings.upload_dir, str)
        assert isinstance(settings.processed_dir, str)
        assert isinstance(settings.temp_dir, str)

    def test_directories_are_non_empty(self):
        """Diretórios devem ser caminhos não vazios"""
        settings = get_settings()
        assert len(settings.upload_dir) > 0
        assert len(settings.processed_dir) > 0
        assert len(settings.temp_dir) > 0


class TestRedisConfiguration:
    """Testes para configuração do Redis"""

    def test_redis_url_format(self):
        """URL do Redis deve ter formato válido"""
        settings = get_settings()
        assert settings.redis_url.startswith("redis://")

    def test_redis_url_not_empty(self):
        """URL do Redis não deve estar vazia"""
        settings = get_settings()
        assert len(settings.redis_url) > 0


class TestNormalizationSettings:
    """Testes para parâmetros de normalização"""

    def test_chunk_duration_is_positive(self):
        """Duração do chunk deve ser positiva"""
        settings = get_settings()
        assert settings.audio_chunk_duration_sec > 0

    def test_noise_reduction_sample_rate(self):
        """Taxa de amostragem de redução de ruído deve ser positiva"""
        settings = get_settings()
        assert settings.noise_reduction_sample_rate > 0
