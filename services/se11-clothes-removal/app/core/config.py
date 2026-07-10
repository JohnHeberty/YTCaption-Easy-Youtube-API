"""Application configuration for SE11 Clothes Removal."""
from __future__ import annotations

from functools import lru_cache

from pydantic import ConfigDict

from common.config_utils.base_settings import BaseServiceSettings


class ClothesRemovalSettings(BaseServiceSettings):
    """Settings for the Clothes Removal service.

    Inherits: app_name, host, port, redis_url, api_key, log_level, log_dir, etc.
    """

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    # === SE10 (Clothes Segmentation) ===
    se10_url: str = "http://localhost:8010"
    se10_api_key: str = "se10-test-key-2026"
    se10_timeout: int = 60

    # === SE8 (Image Generation / Inpainting) ===
    se8_url: str = "http://localhost:8008"
    se8_api_key: str = "se8-test-key-2026"
    se8_timeout: int = 300

    # === Timeout & Concurrency ===
    se10_poll_interval: int = 3
    se8_poll_interval: int = 5
    max_concurrent_jobs: int = 2

    # === AI Image Detection ===
    ai_detection_enabled: bool = True

    # === Face Restoration ===
    face_restore_default: bool = False

    def __getitem__(self, key: str) -> object:
        return getattr(self, key, None)


@lru_cache()
def get_settings() -> ClothesRemovalSettings:
    return ClothesRemovalSettings()


settings = get_settings()
