from functools import lru_cache
from typing import Any, Optional

from common.config_utils.base_settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    """Video Downloader Service settings — validated & loaded from environment variables."""

    # Application
    app_name: str = "Video Downloader Service"
    app_version: str = "2.0.0"
    environment: str = "development"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8002

    # Processing limits
    cache_ttl_hours: int = 24
    max_file_size_mb: int = 10240
    max_concurrent_downloads: int = 2
    default_quality: str = "best"
    job_processing_timeout_seconds: int = 1800

    # Directories
    cache_dir: str = "./data/cache"
    downloads_dir: str = "./data/downloads"
    log_dir: str = "./data/logs"

    # Logging
    log_format: str = "json"

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period: int = 60

    # ------------------------------------------------------------------ #
    #  Backward-compatibility helpers (callers use settings['key'] style)  #
    # ------------------------------------------------------------------ #
    @property
    def rate_limit(self) -> dict:
        return {
            "enabled": self.rate_limit_enabled,
            "max_requests": self.rate_limit_requests,
            "window_seconds": self.rate_limit_period,
        }

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return singleton Settings instance (type-validated, cached)."""
    return Settings()
