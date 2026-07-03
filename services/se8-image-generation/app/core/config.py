from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator

from common.config_utils.base_settings import BaseServiceSettings


class ImageEngineSettings(BaseServiceSettings):
    app_name: str = "SE8 Image Engine"
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8008
    workers: int = 1

    # GPU
    gpu_mode: str = Field(default="lazy", env="GPU_MODE")  # lazy | eager | auto
    gpu_device_id: int | None = Field(default=None, env="GPU_DEVICE_ID")
    max_vram_mb: int = Field(default=0, env="MAX_VRAM_MB")  # 0 = auto-detect
    model_idle_timeout: int = Field(default=60, env="MODEL_IDLE_TIMEOUT")  # seconds

    # Paths
    output_dir: str = Field(default="./data/outputs", env="OUTPUT_DIR")
    model_dir: str = Field(default="./data/models", env="MODEL_DIR")
    temp_dir: str = Field(default="./data/temp", env="TEMP_DIR")

    # Queue
    max_queue_size: int = 100

    # Auth
    se8_api_key: str | None = Field(default=None, env="SE8_API_KEY")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/8", env="REDIS_URL")

    # Celery
    celery_broker_url: str | None = Field(default=None, env="CELERY_BROKER_URL")
    celery_result_backend: str | None = Field(default=None, env="CELERY_RESULT_BACKEND")

    # Generation defaults
    default_performance: str = Field(default="Speed", env="DEFAULT_PERFORMANCE")
    default_cfg_scale: float = Field(default=4.0, env="DEFAULT_CFG_SCALE")
    default_sharpness: float = Field(default=2.0, env="DEFAULT_SHARPNESS")
    default_width: int = Field(default=1024, env="DEFAULT_WIDTH")
    default_height: int = Field(default=1024, env="DEFAULT_HEIGHT")
    default_base_model: str = Field(
        default="juggernautXL_v8Rundiffusion.safetensors", env="DEFAULT_BASE_MODEL"
    )
    default_refiner_model: str = Field(default="None", env="DEFAULT_REFINER_MODEL")

    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "allow"}

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


@lru_cache()
def get_settings() -> ImageEngineSettings:
    return ImageEngineSettings()
