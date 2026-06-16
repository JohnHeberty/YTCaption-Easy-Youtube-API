from functools import lru_cache
from typing import Optional

from pydantic import Field

from common.config_utils.base_settings import BaseServiceSettings


class ImageGenerationSettings(BaseServiceSettings):
    app_name: str = "Image Generation Service"
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8008
    workers: int = 1

    fooocus_api_url: str = Field(default="http://fooocus-api:8888", env="FOOOCUS_API_URL")
    fooocus_api_key: Optional[str] = Field(default=None, env="FOOOCUS_API_KEY")
    se8_api_key: Optional[str] = Field(default=None, env="SE8_API_KEY")

    default_performance: str = Field(default="Speed", env="DEFAULT_PERFORMANCE")
    default_prompt_negative: str = ""
    default_cfg_scale: float = Field(default=4.0, env="DEFAULT_CFG_SCALE")
    default_sharpness: float = Field(default=2.0, env="DEFAULT_SHARPNESS")
    default_width: int = Field(default=1024, env="DEFAULT_WIDTH")
    default_height: int = Field(default=1024, env="DEFAULT_HEIGHT")
    max_image_number: int = Field(default=4, env="MAX_IMAGE_NUMBER")
    max_queue_size: int = 100

    output_dir: str = Field(default="./data/outputs", env="OUTPUT_DIR")
    model_dir: str = Field(default="./data/models", env="MODEL_DIR")
    temp_dir: str = Field(default="./data/temp", env="TEMP_DIR")

    redis_url: str = Field(default="redis://localhost:6379/8", env="REDIS_URL")
    celery_broker_url: Optional[str] = Field(default=None, env="CELERY_BROKER_URL")
    celery_result_backend: Optional[str] = Field(default=None, env="CELERY_RESULT_BACKEND")

    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

    def __getitem__(self, key: str):
        return getattr(self, key, None)


@lru_cache()
def get_settings() -> ImageGenerationSettings:
    return ImageGenerationSettings()
