from __future__ import annotations

from functools import lru_cache
from typing import Any

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
    youtube_default_timeout: int = Field(default=10)
    youtube_max_results: int = Field(default=50)
    youtube_max_videos_per_channel: int = Field(default=100)
    youtube_innertube_api_key: str = Field(
        default="AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8",
    )

    # Cache
    cache_ttl_hours: int = 24
    cache_cleanup_interval_minutes: int = 30
    cache_max_size_mb: int = 512

    # Rate limiting
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests: int = Field(default=100)
    rate_limit_period: int = Field(default=60)

    # Logging
    log_dir: str = "./data/logs"

    # Timeouts
    async_timeout_seconds: int = Field(default=120)
    job_processing_timeout_seconds: int = Field(default=300)
    poll_interval_seconds: int = Field(default=2)

    # Celery
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    celery_task_time_limit: int = Field(default=600)
    celery_task_soft_time_limit: int = Field(default=500)

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


@lru_cache(maxsize=1)
def get_settings() -> ServiceSettings:
    """Returns the typed Pydantic settings instance."""
    return _core


def validate_settings() -> bool:
    """Validate that settings loaded correctly. Returns True if OK."""
    s = get_settings()
    assert s.port > 0
    assert s.app_name
    return True
