"""
Testes unitários para Config.
"""
import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from core.config import OrchestratorSettings, get_settings, get_microservice_config


class TestOrchestratorSettings:
    """Testes para OrchestratorSettings."""

    def test_required_urls(self):
        """Deve exigir URLs de microserviços."""
        # URLs are loaded from .env - this test verifies the model validates URLs when provided
        with patch.dict(os.environ, {
            "VIDEO_DOWNLOADER_URL": "http://localhost:8001",
            "AUDIO_NORMALIZATION_URL": "http://localhost:8002",
            "AUDIO_TRANSCRIBER_URL": "http://localhost:8003",
        }, clear=True):
            from core.config import get_settings
            get_settings.cache_clear()
            settings = OrchestratorSettings()
            assert settings.video_downloader_url is not None

    def test_valid_urls(self):
        """Deve aceitar URLs válidas."""
        with patch.dict(os.environ, {}, clear=True):
            settings = OrchestratorSettings(
                video_downloader_url="http://localhost:8001",
                audio_normalization_url="http://localhost:8002",
                audio_transcriber_url="http://localhost:8003",
            )
            assert settings.video_downloader_url == "http://localhost:8001"

    def test_url_validator(self):
        """Deve validar formato de URL."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                OrchestratorSettings(
                    video_downloader_url="not-a-url",
                    audio_normalization_url="http://localhost:8002",
                    audio_transcriber_url="http://localhost:8003",
                )
            assert "URL must start with http" in str(exc_info.value)

    def test_url_strips_trailing_slash(self):
        """Deve remover barra final da URL."""
        with patch.dict(os.environ, {}, clear=True):
            settings = OrchestratorSettings(
                video_downloader_url="http://localhost:8001/",
                audio_normalization_url="http://localhost:8002/",
                audio_transcriber_url="http://localhost:8003/",
            )
            assert settings.video_downloader_url == "http://localhost:8001"

    def test_defaults(self):
        """Deve ter valores padrão razoáveis."""
        with patch.dict(os.environ, {}, clear=True):
            settings = OrchestratorSettings(
                video_downloader_url="http://localhost:8001",
                audio_normalization_url="http://localhost:8002",
                audio_transcriber_url="http://localhost:8003",
            )
            assert settings.app_port == 8080
            assert settings.redis_url.startswith("redis://")
            assert settings.debug is False

    def test_ssl_config(self):
        """Deve ter configuração SSL."""
        with patch.dict(os.environ, {}, clear=True):
            settings = OrchestratorSettings(
                video_downloader_url="http://localhost:8001",
                audio_normalization_url="http://localhost:8002",
                audio_transcriber_url="http://localhost:8003",
                ssl_verify=True,
                ssl_cert_path=None,
            )
            assert settings.ssl_verify is True


class TestMicroserviceConfig:
    """Testes para get_microservice_config."""

    def test_video_downloader_config(self):
        """Deve retornar config do video-downloader."""
        with patch.dict(os.environ, {
            "VIDEO_DOWNLOADER_URL": "http://localhost:8001",
            "AUDIO_NORMALIZATION_URL": "http://localhost:8002",
            "AUDIO_TRANSCRIBER_URL": "http://localhost:8003",
        }, clear=True):
            get_settings.cache_clear()
            config = get_microservice_config("video-downloader")
            assert config["url"] == "http://localhost:8001"
            assert "endpoints" in config
            assert "submit" in config["endpoints"]

    def test_audio_normalization_config(self):
        """Deve retornar config do audio-normalization."""
        with patch.dict(os.environ, {
            "VIDEO_DOWNLOADER_URL": "http://localhost:8001",
            "AUDIO_NORMALIZATION_URL": "http://localhost:8002",
            "AUDIO_TRANSCRIBER_URL": "http://localhost:8003",
        }, clear=True):
            get_settings.cache_clear()
            config = get_microservice_config("audio-normalization")
            assert config["url"] == "http://localhost:8002"
            assert "default_params" in config

    def test_audio_transcriber_config(self):
        """Deve retornar config do audio-transcriber."""
        with patch.dict(os.environ, {
            "VIDEO_DOWNLOADER_URL": "http://localhost:8001",
            "AUDIO_NORMALIZATION_URL": "http://localhost:8002",
            "AUDIO_TRANSCRIBER_URL": "http://localhost:8003",
        }, clear=True):
            get_settings.cache_clear()
            config = get_microservice_config("audio-transcriber")
            assert config["url"] == "http://localhost:8003"
            assert "text" in config["endpoints"]
            assert "transcription" in config["endpoints"]

    def test_unknown_service_returns_empty(self):
        """Deve retornar dict vazio para serviço desconhecido."""
        with patch.dict(os.environ, {
            "VIDEO_DOWNLOADER_URL": "http://localhost:8001",
            "AUDIO_NORMALIZATION_URL": "http://localhost:8002",
            "AUDIO_TRANSCRIBER_URL": "http://localhost:8003",
        }, clear=True):
            get_settings.cache_clear()
            config = get_microservice_config("unknown-service")
            assert config == {}


class TestGetSettings:
    """Testes para get_settings."""

    def test_singleton(self):
        """Deve retornar mesma instância."""
        # Limpa cache para teste
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2
