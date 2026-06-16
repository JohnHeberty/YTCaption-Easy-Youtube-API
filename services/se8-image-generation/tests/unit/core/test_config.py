import pytest
from app.core.config import ImageGenerationSettings, get_settings


class TestImageGenerationSettings:
    def test_default_values(self):
        settings = ImageGenerationSettings()
        assert settings.app_name == "Image Generation Service"
        assert settings.version == "1.0.0"
        assert settings.environment == "development"
        assert settings.debug is False

    def test_default_network(self):
        settings = ImageGenerationSettings()
        assert settings.host == "0.0.0.0"
        assert settings.port == 8008
        assert settings.workers == 1

    def test_default_generation(self):
        settings = ImageGenerationSettings()
        assert settings.default_performance == "Speed"
        assert settings.default_cfg_scale == 4.0
        assert settings.default_sharpness == 2.0
        assert settings.default_width == 1024
        assert settings.default_height == 1024
        assert settings.max_image_number == 4

    def test_default_paths(self):
        settings = ImageGenerationSettings()
        assert settings.output_dir == "./data/outputs"
        assert settings.model_dir == "./data/models"
        assert settings.temp_dir == "./data/temp"

    def test_getitem(self):
        settings = ImageGenerationSettings()
        assert settings["port"] == 8008
        assert settings["nonexistent"] is None

    def test_settings_from_env(self, monkeypatch):
        monkeypatch.setenv("SE8_API_KEY", "custom-key")
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.se8_api_key == "custom-key"
        get_settings.cache_clear()

    def test_fooocus_url_from_env(self, monkeypatch):
        monkeypatch.setenv("FOOOCUS_API_URL", "http://custom:9999")
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.fooocus_api_url == "http://custom:9999"
        get_settings.cache_clear()


class TestGetSettings:
    def test_returns_same_instance(self):
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_cache_clear_returns_new(self):
        get_settings.cache_clear()
        s1 = get_settings()
        get_settings.cache_clear()
        s2 = get_settings()
        assert s1 is not s2
