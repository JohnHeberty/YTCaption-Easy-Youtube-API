"""SE10 Clothes Segmentation — service settings."""

from functools import lru_cache
from typing import Optional

from pydantic import Field

from common.config_utils.base_settings import BaseServiceSettings


class ClothesSegSettings(BaseServiceSettings):
    """Configuration for the Clothes Segmentation service."""

    app_name: str = "SE10 Clothes Segmentation"
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8010
    workers: int = 1

    # ML / Model
    device: str = Field(default="auto", env="DEVICE")  # auto | cpu | cuda
    checkpoint_dir: str = Field(default="./checkpoints", env="CHECKPOINT_DIR")
    external_dir: str = Field(default="./external", env="EXTERNAL_DIR")

    # Segmentation parameters
    box_threshold: float = Field(default=0.10, env="BOX_THRESHOLD")
    text_threshold: float = Field(default=0.10, env="TEXT_THRESHOLD")
    max_area_pct: float = Field(default=0.29, env="MAX_AREA_PCT")
    max_objects: int = Field(default=50, env="MAX_OBJECTS")

    # Worker
    worker_threads: int = Field(default=2, env="WORKER_THREADS")

    # Auth
    se10_api_key: Optional[str] = Field(default=None, env="SE10_API_KEY")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/10", env="REDIS_URL")

    # Paths
    output_dir: str = Field(default="./data/outputs", env="OUTPUT_DIR")
    temp_dir: str = Field(default="./data/temp", env="TEMP_DIR")

    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

    def __getitem__(self, key: str):
        return getattr(self, key, None)


@lru_cache()
def get_settings() -> ClothesSegSettings:
    return ClothesSegSettings()
