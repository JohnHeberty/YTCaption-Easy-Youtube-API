"""Application configuration using BaseServiceSettings from shared library."""
from __future__ import annotations

from functools import lru_cache

from pydantic import ConfigDict, Field

from common.config_utils.base_settings import BaseServiceSettings

from app.core.constants import DEFAULT_VOICE_ID


class MakeVideoImgSettings(BaseServiceSettings):
    """Core settings for the Make Video IMG service.

    Inherits from BaseServiceSettings: app_name, app_version, environment,
    debug, host, port, workers, redis_url, api_key, tz, log_level, log_dir,
    output_dir, temp_dir, divisor.
    """

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    # === SE7 (Audio Generation) ===
    se7_url: str = "http://localhost:8007"
    se7_api_key: str = "se7-test-key-2026"

    # === SE8 (Image Generation) ===
    se8_url: str = "http://localhost:8008"
    se8_api_key: str = "se8-test-key-2026"

    # === VIDEO DEFAULTS ===
    default_voice_id: str = DEFAULT_VOICE_ID
    default_aspect_ratio: str = "9:16"
    default_width: int = 1080
    default_height: int = 1920
    default_fps: int = 30
    default_zoom_speed: float = 0.004
    default_crossfade_duration: float = 0.3
    default_image_steps: int = 30
    default_image_performance: str = "Quality"

    # === EXTERNAL URL (for webhooks) ===
    external_url: str = ""

    # === TITLE CARD ===
    title_card_duration: float = 0.5

    # === TTS PARAMS (passed to SE7) ===
    tts_exaggeration: float = 0.5
    tts_cfg_weight: float = 0.5
    tts_temperature: float = 0.8
    default_normalize_text: bool = False

    # === TIMEOUTS (seconds) ===
    se7_poll_interval: int = 5
    se7_timeout: int = 600
    se8_poll_interval: int = 3
    se8_timeout: int = 300
    ffmpeg_segment_timeout: int = 60
    ffmpeg_total_timeout: int = 300

    def __getitem__(self, key: str) -> object:
        return getattr(self, key, None)


@lru_cache()
def get_settings() -> MakeVideoImgSettings:
    return MakeVideoImgSettings()


settings = get_settings()
