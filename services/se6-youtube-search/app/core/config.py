from functools import lru_cache
from typing import Any, Dict, Optional

from pydantic import Field, field_validator

from common.config_utils.base_settings import BaseServiceSettings


class ServiceSettings(BaseServiceSettings):
    """YouTube Search Service settings — validated & loaded from environment variables."""

    app_name: str = "YouTube Search Service"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8006

    # YouTube API
    youtube_default_timeout: int = Field(default=10, env="YOUTUBE_DEFAULT_TIMEOUT")
    youtube_max_results: int = Field(default=50, env="YOUTUBE_MAX_RESULTS")
    youtube_max_videos_per_channel: int = Field(default=100, env="YOUTUBE_MAX_VIDEOS_PER_CHANNEL")
    youtube_innertube_api_key: str = Field(
        default="AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8",
        env="YOUTUBE_INNERTUBE_API_KEY",
    )

    # Cache
    cache_ttl_hours: int = 24
    cache_cleanup_interval_minutes: int = 30
    cache_max_size_mb: int = 512

    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(default=60, env="RATE_LIMIT_PERIOD")

    # Logging
    log_dir: str = "./logs"

    # Timeouts
    async_timeout_seconds: int = Field(default=120, env="ASYNC_TIMEOUT_SECONDS")
    job_processing_timeout_seconds: int = Field(default=300, env="JOB_PROCESSING_TIMEOUT_SECONDS")
    poll_interval_seconds: int = Field(default=2, env="POLL_INTERVAL_SECONDS")

    # Celery
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None
    celery_task_time_limit: int = Field(default=600, env="CELERY_TASK_TIME_LIMIT")
    celery_task_soft_time_limit: int = Field(default=500, env="CELERY_TASK_SOFT_TIME_LIMIT")

    @field_validator("port")
    @classmethod
    def port_must_be_valid(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"PORT must be 1-65535, got {v}")
        return v

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key, None)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


_core = ServiceSettings()


def _build_legacy_dict(s: ServiceSettings) -> Dict[str, Any]:
    """Build backward-compatible dict with nested structures for callers
    that use settings['youtube']['key'] style."""
    return {
        'app_name': s.app_name,
        'version': s.app_version,
        'environment': s.environment,
        'debug': s.debug,
        'host': s.host,
        'port': s.port,
        'api_key': s.api_key,
        'redis_url': s.redis_url,
        'celery': {
            'broker_url': s.celery_broker_url or s.redis_url,
            'result_backend': s.celery_result_backend or s.redis_url,
            'task_serializer': 'json',
            'result_serializer': 'json',
            'accept_content': ['json'],
            'timezone': s.tz,
            'enable_utc': False,
            'task_track_started': True,
            'task_time_limit': s.celery_task_time_limit,
            'task_soft_time_limit': s.celery_task_soft_time_limit,
            'worker_prefetch_multiplier': 1,
            'worker_max_tasks_per_child': 100,
        },
        'cache_ttl_hours': s.cache_ttl_hours,
        'cache_cleanup_interval_minutes': s.cache_cleanup_interval_minutes,
        'cache_max_size_mb': s.cache_max_size_mb,
        'youtube': {
            'default_timeout': s.youtube_default_timeout,
            'max_results': s.youtube_max_results,
            'max_videos_per_channel': s.youtube_max_videos_per_channel,
            'innertube_api_key': s.youtube_innertube_api_key,
        },
        'rate_limit': {
            'enabled': s.rate_limit_enabled,
            'requests_per_minute': s.rate_limit_requests,
            'period_seconds': s.rate_limit_period,
        },
        'timeouts': {
            'async_timeout_sec': s.async_timeout_seconds,
            'job_processing_timeout_sec': s.job_processing_timeout_seconds,
            'poll_interval_sec': s.poll_interval_seconds,
        },
        'log_level': s.log_level,
        'log_format': 'json',
        'log_dir': s.log_dir,
        'cors': {
            'enabled': True,
            'origins': ['*'],
            'credentials': True,
            'methods': ['*'],
            'headers': ['*'],
        },
        'health_check': {
            'enabled': True,
            'interval_seconds': 30,
        },
    }


@lru_cache(maxsize=1)
def get_settings() -> Dict[str, Any]:
    """Returns backward-compatible dict with nested structures."""
    return _build_legacy_dict(_core)
