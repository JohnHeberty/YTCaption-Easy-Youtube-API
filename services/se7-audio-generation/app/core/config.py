from functools import lru_cache
from typing import Optional

from pydantic import Field

from common.config_utils.base_settings import BaseServiceSettings


class AudioGenSettings(BaseServiceSettings):
    app_name: str = "Audio Generation Service"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8007

    # SE7-specific
    huggingface_token: Optional[str] = Field(default=None)
    model_name: str = "ResembleAI/Chatterbox-Multilingual-pt-br"
    model_dir: str = "./data/models"
    device: str = "auto"

    default_exaggeration: float = Field(default=0.5, ge=0.0, le=2.0)
    default_cfg_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    default_temperature: float = Field(default=0.8, ge=0.0, le=2.0)
    max_text_length: int = Field(default=5000, ge=100, le=50000)
    chunk_size: int = Field(default=1000, ge=50, le=5000)

    output_dir: str = "./data/outputs"
    voices_dir: str = "./data/voices"

    min_voice_sample_duration: float = Field(default=5.0, ge=1.0, le=30.0)
    max_voice_sample_duration: float = Field(default=15.0, ge=1.0, le=60.0)
    max_voice_file_size_mb: int = Field(default=10, ge=1, le=50)

    def __getitem__(self, key: str):
        return getattr(self, key, None)


@lru_cache()
def get_settings() -> AudioGenSettings:
    return AudioGenSettings()
