from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Video Downloader Service settings — validated & loaded from environment variables."""

    # Application
    app_name: str = "Video Downloader Service"
    version: str = "2.0.0"
    environment: str = "development"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8002

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Processing limits
    cache_ttl_hours: int = 24
    max_file_size_mb: int = 10240
    max_concurrent_downloads: int = 2
    default_quality: str = "best"
    job_processing_timeout_seconds: int = 1800

    # Directories
    cache_dir: str = "./cache"
    downloads_dir: str = "./downloads"
    temp_dir: str = "./temp"
    log_dir: str = "./logs"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # ------------------------------------------------------------------ #
    #  Backward-compatibility helpers (callers use settings['key'] style)  #
    # ------------------------------------------------------------------ #
    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return singleton Settings instance (type-validated, cached)."""
    return Settings()
