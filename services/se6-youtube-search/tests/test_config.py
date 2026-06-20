"""
Tests for config module
"""
import pytest
from app.core.config import get_settings, validate_settings


def test_get_settings():
    """Test getting settings"""
    settings = get_settings()

    assert settings is not None
    assert settings.app_name is not None
    assert settings.redis_url is not None
    assert settings.cache_ttl_hours >= 1


def test_settings_defaults():
    """Test default settings values"""
    settings = get_settings()

    assert settings.cache_ttl_hours >= 1
    assert settings.port > 0
    assert settings.youtube_default_timeout > 0


def test_settings_youtube_config():
    """Test YouTube specific settings"""
    settings = get_settings()

    assert settings.youtube_default_timeout > 0
    assert settings.youtube_max_results > 0
    assert settings.youtube_innertube_api_key is not None


def test_settings_celery_config():
    """Test Celery specific settings"""
    settings = get_settings()

    assert settings.celery_task_time_limit > 0
    assert settings.celery_task_soft_time_limit > 0


def test_validate_settings():
    """Test settings validation"""
    result = validate_settings()
    assert result is True
