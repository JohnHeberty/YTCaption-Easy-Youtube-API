from functools import lru_cache
from pathlib import Path
from typing import Dict, Any

from pydantic import Field

from common.config_utils.base_settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    """Make-Video-Clip Service settings."""

    # Service Info
    app_name: str = "make-video-clip"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8005

    # Redis
    cache_ttl_hours: int = 24
    max_cache_size_gb: int = 50

    # Microservices URLs
    youtube_search_url: str = "http://localhost:8006"
    video_downloader_url: str = "http://localhost:8002"
    audio_transcriber_url: str = "http://localhost:8004"

    # Storage
    audio_upload_dir: str = "./data/raw/audio"
    shorts_cache_dir: str = "./data/raw/shorts"
    transform_dir: str = "./data/transform/videos"
    validate_dir: str = "./data/validate"
    approved_dir: str = "./data/approved/videos"
    output_dir: str = "./data/approved/output"
    log_dir: str = "./data/logs"

    # Logging
    log_format: str = "json"

    # Video Processing
    default_aspect_ratio: str = "9:16"
    default_crop_position: str = "center"
    default_video_quality: str = "fast"

    # Cleanup
    cleanup_temp_after_hours: int = 1
    cleanup_output_after_hours: int = 24
    cleanup_shorts_cache_after_days: int = 30

    # Video Compatibility
    target_video_height: int = 720
    target_video_width: int = 1280
    target_video_fps: float = 30.0
    target_video_codec: str = "h264"

    # SQLite (DEPRECATED)
    sqlite_db_path: str = "./data/raw/shorts/blacklist.db"
    video_status_db_path: str = "./data/database/video_status.db"

    # Subtitle
    subtitle_font_size: int = 22
    subtitle_font_name: str = "Arial Black"
    subtitle_color: str = "&H00FFFF&"
    subtitle_outline_color: str = "&H000000&"
    subtitle_outline: int = 2
    subtitle_alignment: int = 10
    subtitle_margin_v: int = 280
    words_per_caption: int = 1

    # OCR
    ocr_confidence_threshold: float = 0.50
    ocr_frames_per_second: int = 3
    ocr_max_frames: int = 240

    # TRSD
    trsd_enabled: bool = False
    trsd_downscale_width: int = 640
    trsd_min_text_length: int = 2
    trsd_min_confidence: float = 0.50
    trsd_min_alpha_ratio: float = 0.60
    trsd_line_y_tolerance: int = 10
    trsd_line_x_gap: int = 50
    trsd_track_iou_threshold: float = 0.30
    trsd_track_max_distance: int = 50
    trsd_ignore_static_text: bool = True
    trsd_static_min_presence: float = 0.85
    trsd_static_max_change: float = 0.10
    trsd_subtitle_min_change_rate: float = 0.25
    trsd_screencast_min_detections: int = 10
    trsd_save_detection_events: bool = False
    trsd_save_debug_artifacts: bool = False

    # VAD
    vad_threshold: float = 0.5
    vad_model: str = "webrtc"

    # FFmpeg
    ffmpeg_video_codec: str = "libx264"
    ffmpeg_audio_codec: str = "aac"
    ffmpeg_preset: str = "fast"
    ffmpeg_crf: int = 23

    # Video Trimming
    video_trim_padding_ms: int = 1000

    # Celery Worker
    celery_worker_concurrency: int = 4
    celery_worker_prefetch_multiplier: int = 1
    celery_task_time_limit: int = 3600

    # API Timeouts
    api_timeout: int = 120
    download_poll_interval: int = 3
    download_max_polls: int = 40
    transcribe_poll_interval: int = 5
    transcribe_max_polls: int = 240

    # Video Fetch
    max_fetch_rounds: int = 10

    def __getitem__(self, key: str):
        return getattr(self, key, None)

    def get(self, key: str, default=None):
        return getattr(self, key, default)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns the typed Pydantic settings instance."""
    return Settings()


def ensure_directories():
    """Cria diretórios necessários se não existirem"""
    settings = get_settings()
    for dir_path in [settings.audio_upload_dir, settings.shorts_cache_dir,
                     settings.output_dir, settings.log_dir]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
