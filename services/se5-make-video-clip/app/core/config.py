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
    log_dir: str = "./logs"

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
def get_settings() -> Dict[str, Any]:
    """Returns backward-compatible dict."""
    s = Settings()
    return {
        "service_name": s.app_name,
        "version": s.app_version,
        "api_key": s.api_key,
        "port": s.port,
        "debug": s.debug,
        "redis_url": s.redis_url,
        "cache_ttl_hours": s.cache_ttl_hours,
        "max_cache_size_gb": s.max_cache_size_gb,
        "youtube_search_url": s.youtube_search_url,
        "video_downloader_url": s.video_downloader_url,
        "audio_transcriber_url": s.audio_transcriber_url,
        "audio_upload_dir": s.audio_upload_dir,
        "shorts_cache_dir": s.shorts_cache_dir,
        "transform_dir": s.transform_dir,
        "validate_dir": s.validate_dir,
        "approved_dir": s.approved_dir,
        "output_dir": s.output_dir,
        "log_level": s.log_level,
        "logs_dir": s.log_dir,
        "log_dir": s.log_dir,
        "log_format": s.log_format,
        "default_aspect_ratio": s.default_aspect_ratio,
        "default_crop_position": s.default_crop_position,
        "default_video_quality": s.default_video_quality,
        "cleanup_temp_after_hours": s.cleanup_temp_after_hours,
        "cleanup_output_after_hours": s.cleanup_output_after_hours,
        "cleanup_shorts_cache_after_days": s.cleanup_shorts_cache_after_days,
        "target_video_height": s.target_video_height,
        "target_video_width": s.target_video_width,
        "target_video_fps": s.target_video_fps,
        "target_video_codec": s.target_video_codec,
        "sqlite_db_path": s.sqlite_db_path,
        "video_status_db_path": s.video_status_db_path,
        "subtitle_font_size": s.subtitle_font_size,
        "subtitle_font_name": s.subtitle_font_name,
        "subtitle_color": s.subtitle_color,
        "subtitle_outline_color": s.subtitle_outline_color,
        "subtitle_outline": s.subtitle_outline,
        "subtitle_alignment": s.subtitle_alignment,
        "subtitle_margin_v": s.subtitle_margin_v,
        "words_per_caption": s.words_per_caption,
        "ocr_confidence_threshold": s.ocr_confidence_threshold,
        "ocr_frames_per_second": s.ocr_frames_per_second,
        "ocr_max_frames": s.ocr_max_frames,
        "vad_threshold": s.vad_threshold,
        "vad_model": s.vad_model,
        "ffmpeg_video_codec": s.ffmpeg_video_codec,
        "ffmpeg_audio_codec": s.ffmpeg_audio_codec,
        "ffmpeg_preset": s.ffmpeg_preset,
        "ffmpeg_crf": s.ffmpeg_crf,
        "celery_worker_concurrency": s.celery_worker_concurrency,
        "celery_worker_prefetch_multiplier": s.celery_worker_prefetch_multiplier,
        "celery_task_time_limit": s.celery_task_time_limit,
        "max_fetch_rounds": s.max_fetch_rounds,
        "video_trim_padding_ms": s.video_trim_padding_ms,
    }


def ensure_directories():
    """Cria diretórios necessários se não existirem"""
    settings = get_settings()
    for dir_path in [settings["audio_upload_dir"], settings["shorts_cache_dir"],
                     settings["output_dir"], settings["log_dir"]]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
