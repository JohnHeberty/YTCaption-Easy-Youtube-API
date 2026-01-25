"""
Tests for config module
"""
import pytest
from app.config import get_settings, validate_settings


def test_get_settings():
    """Test getting settings"""
    settings = get_settings()
    
    assert settings is not None
    assert isinstance(settings, dict)
    assert 'app_name' in settings
    assert 'redis_url' in settings
    assert 'cache_ttl_hours' in settings


def test_settings_defaults():
    """Test default settings values"""
    settings = get_settings()
    
    # Check defaults
    assert settings['cache_ttl_hours'] >= 1
    assert settings['port'] > 0
    assert settings['youtube']['default_timeout'] > 0


def test_settings_youtube_config():
    """Test YouTube specific settings"""
    settings = get_settings()
    
    assert 'youtube' in settings
    assert 'default_timeout' in settings['youtube']
    assert 'max_results' in settings['youtube']
    assert 'innertube_api_key' in settings['youtube']


def test_settings_celery_config():
    """Test Celery specific settings"""
    settings = get_settings()
    
    assert 'celery' in settings
    assert 'broker_url' in settings['celery']
    assert 'result_backend' in settings['celery']
    assert 'task_time_limit' in settings['celery']


def test_validate_settings():
    """Test settings validation"""
    # Should not raise any exception
    result = validate_settings()
    assert result is True
