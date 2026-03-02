import os
from functools import lru_cache
from typing import Any, Dict

from pydantic import field_validator
from pydantic_settings import BaseSettings


class _CoreSettings(BaseSettings):
    """Validates critical typed settings at startup (fail-fast)."""

    app_name: str = "YouTube Search Service"
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8001
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"

    @field_validator("port")
    @classmethod
    def port_must_be_valid(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"PORT must be 1-65535, got {v}")
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Validate critical settings at import time — raises ValidationError on bad env vars
_core = _CoreSettings()


@lru_cache(maxsize=1)
def get_settings() -> Dict[str, Any]:
    """
    Returns all service settings from environment variables.
    Result is cached (singleton) — env changes after first call are ignored.
    Configurations organized by category for easy maintenance.
    """
    return {
        # ===== APPLICATION =====
        'app_name': os.getenv('APP_NAME', 'YouTube Search Service'),
        'version': os.getenv('VERSION', '1.0.0'),
        'environment': os.getenv('ENVIRONMENT', 'development'),
        'debug': os.getenv('DEBUG', 'false').lower() == 'true',
        'host': os.getenv('HOST', '0.0.0.0'),
        'port': int(os.getenv('PORT', '8003')),
        
        # ===== REDIS =====
        'redis_url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        
        # ===== CELERY =====
        'celery': {
            'broker_url': os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0')),
            'result_backend': os.getenv('CELERY_RESULT_BACKEND', os.getenv('REDIS_URL', 'redis://localhost:6379/0')),
            'task_serializer': os.getenv('CELERY_TASK_SERIALIZER', 'json'),
            'result_serializer': os.getenv('CELERY_RESULT_SERIALIZER', 'json'),
            'accept_content': os.getenv('CELERY_ACCEPT_CONTENT', 'json').split(','),
            'timezone': os.getenv('CELERY_TIMEZONE', 'UTC'),
            'enable_utc': os.getenv('CELERY_ENABLE_UTC', 'true').lower() == 'true',
            'task_track_started': os.getenv('CELERY_TASK_TRACK_STARTED', 'true').lower() == 'true',
            'task_time_limit': int(os.getenv('CELERY_TASK_TIME_LIMIT', '600')),
            'task_soft_time_limit': int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', '500')),
            'worker_prefetch_multiplier': int(os.getenv('CELERY_WORKER_PREFETCH_MULTIPLIER', '1')),
            'worker_max_tasks_per_child': int(os.getenv('CELERY_WORKER_MAX_TASKS_PER_CHILD', '100')),
        },
        
        # ===== CACHE =====
        'cache_ttl_hours': int(os.getenv('CACHE_TTL_HOURS', '24')),
        'cache_cleanup_interval_minutes': int(os.getenv('CACHE_CLEANUP_INTERVAL_MINUTES', '30')),
        'cache_max_size_mb': int(os.getenv('CACHE_MAX_SIZE_MB', '512')),
        
        # ===== YOUTUBE API =====
        'youtube': {
            'default_timeout': int(os.getenv('YOUTUBE_DEFAULT_TIMEOUT', '10')),
            'max_results': int(os.getenv('YOUTUBE_MAX_RESULTS', '50')),
            'max_videos_per_channel': int(os.getenv('YOUTUBE_MAX_VIDEOS_PER_CHANNEL', '100')),
            'innertube_api_key': os.getenv('YOUTUBE_INNERTUBE_API_KEY', 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'),
        },
        
        # ===== RATE LIMITING =====
        'rate_limit': {
            'enabled': os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true',
            'requests_per_minute': int(os.getenv('RATE_LIMIT_REQUESTS', '100')),
            'period_seconds': int(os.getenv('RATE_LIMIT_PERIOD', '60')),
        },
        
        # ===== TIMEOUTS =====
        'timeouts': {
            'async_timeout_sec': int(os.getenv('ASYNC_TIMEOUT_SECONDS', '120')),
            'job_processing_timeout_sec': int(os.getenv('JOB_PROCESSING_TIMEOUT_SECONDS', '300')),
            'poll_interval_sec': int(os.getenv('POLL_INTERVAL_SECONDS', '2')),
        },
        
        # ===== LOGGING =====
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'log_format': os.getenv('LOG_FORMAT', 'json'),
        'log_dir': os.getenv('LOG_DIR', './data/logs'),
        
        # ===== CORS =====
        'cors': {
            'enabled': os.getenv('CORS_ENABLED', 'true').lower() == 'true',
            'origins': os.getenv('CORS_ORIGINS', '*').split(','),
            'credentials': os.getenv('CORS_CREDENTIALS', 'true').lower() == 'true',
            'methods': os.getenv('CORS_METHODS', '*').split(','),
            'headers': os.getenv('CORS_HEADERS', '*').split(','),
        },
        
        # ===== HEALTH CHECK =====
        'health_check': {
            'enabled': os.getenv('HEALTH_CHECK_ENABLED', 'true').lower() == 'true',
            'interval_seconds': int(os.getenv('HEALTH_CHECK_INTERVAL', '30')),
        },
    }


def validate_settings():
    """Validates required settings"""
    settings = get_settings()
    
    # Validate required fields
    required_fields = ['redis_url', 'app_name', 'port']
    for field in required_fields:
        if not settings.get(field):
            raise ValueError(f"Missing required setting: {field}")
    
    return True
