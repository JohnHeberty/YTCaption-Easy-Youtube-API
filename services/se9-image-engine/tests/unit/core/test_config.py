import pytest
from app.core.config import ImageEngineSettings, get_settings


class TestImageEngineSettings:
    def test_default_values(self):
        settings = ImageEngineSettings()
        assert settings.app_name == "SE9 Image Engine"
        assert settings.version == "1.0.0"
        assert settings.environment == "development"
        assert settings.debug is False

    def test_default_network(self):
        settings = ImageEngineSettings()
        assert settings.host == "0.0.0.0"
        assert settings.port == 8009
        assert settings.workers == 1

    def test_default_generation(self):
        settings = ImageEngineSettings()
        assert settings.default_performance == "Speed"
        assert settings.default_cfg_scale == 4.0
        assert settings.default_sharpness == 2.0
        assert settings.default_width == 1024
        assert settings.default_height == 1024

    def test_default_paths(self):
        settings = ImageEngineSettings()
        assert "outputs" in settings.output_dir
        assert "models" in settings.model_dir

    def test_default_gpu(self):
        settings = ImageEngineSettings()
        assert settings.gpu_mode == "lazy"
        assert settings.model_idle_timeout == 300

    def test_getitem(self):
        settings = ImageEngineSettings()
        assert settings["port"] == 8009
        assert settings["nonexistent"] is None

    def test_settings_from_env(self, monkeypatch):
        monkeypatch.setenv("SE9_API_KEY", "custom-key-9")
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.se9_api_key == "custom-key-9"
        get_settings.cache_clear()

    def test_gpu_mode_from_env(self, monkeypatch):
        monkeypatch.setenv("GPU_MODE", "eager")
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.gpu_mode == "eager"
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
