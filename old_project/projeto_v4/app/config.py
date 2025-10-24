import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "YTCaption v3")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    timeout_seconds: float = float(os.getenv("TIMEOUT_SECONDS", "30"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "2"))
    concurrency_limit: int = int(os.getenv("CONCURRENCY_LIMIT", "4"))
    data_dir: str = os.getenv("DATA_DIR", "projeto_v3/data")
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "86400"))  # 1 dia padrão
    cached_only: bool = os.getenv("CACHED_ONLY", "false").lower() in ("1", "true", "yes")


def get_settings() -> Settings:
    return Settings()
