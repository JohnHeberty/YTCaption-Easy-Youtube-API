from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class CoreSettings(BaseSettings):
    app_name: str = "Audio Generation Service"
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8007

    huggingface_token: Optional[str] = Field(default=None)
    model_name: str = "ResembleAI/Chatterbox-Multilingual-pt-br"
    model_dir: str = "./data/models"
    device: str = "auto"

    default_exaggeration: float = Field(default=0.75, ge=0.0, le=2.0)
    default_cfg_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    default_temperature: float = Field(default=0.8, ge=0.0, le=2.0)
    max_text_length: int = Field(default=5000, ge=100, le=50000)
    chunk_size: int = Field(default=250, ge=50, le=1000)

    output_dir: str = "./data/outputs"
    voices_dir: str = "./data/voices"
    temp_dir: str = "./data/temp"

    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None

    log_level: str = "INFO"

    min_voice_sample_duration: float = Field(default=5.0, ge=1.0, le=30.0)
    max_voice_sample_duration: float = Field(default=15.0, ge=1.0, le=60.0)
    max_voice_file_size_mb: int = Field(default=10, ge=1, le=50)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

    def __getitem__(self, key: str):
        return getattr(self, key, None)


@lru_cache()
def get_settings() -> CoreSettings:
    return CoreSettings()
