"""Application configuration using Pydantic Settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    """Core settings for the Make Video IMG service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # === APP ===
    app_name: str = "Make Video IMG"
    version: str = "1.0.0"
    port: int = 8009
    api_key: str = "se9-test-key-2026"
    debug: bool = False

    # === SE7 (Audio Generation) ===
    se7_url: str = "http://localhost:8007"
    se7_api_key: str = "se7-test-key-2026"

    # === SE8 (Image Generation) ===
    se8_url: str = "http://localhost:8008"
    se8_api_key: str = "se8-test-key-2026"

    # === VIDEO DEFAULTS ===
    default_voice_id: str = "builtin_feminino"
    default_aspect_ratio: str = "9:16"
    default_width: int = 1080
    default_height: int = 1920
    default_fps: int = 30
    default_zoom_speed: float = 0.001
    default_crossfade_duration: float = 0.5
    default_image_steps: int = 30
    default_image_performance: str = "Quality"

    # === TIMEOUTS (seconds) ===
    se7_poll_interval: int = 5
    se7_timeout: int = 600
    se8_poll_interval: int = 3
    se8_timeout: int = 300
    ffmpeg_segment_timeout: int = 60
    ffmpeg_total_timeout: int = 300

    # === TEMP FILES ===
    temp_dir: str = "/tmp"

    # === REDIS ===
    redis_url: str = "redis://localhost:6379/9"


settings = CoreSettings()
