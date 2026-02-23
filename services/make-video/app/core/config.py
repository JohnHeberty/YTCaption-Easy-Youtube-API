import os
from pathlib import Path
from typing import Dict, Any
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def expand_env_vars(value: str) -> str:
    """Expand ${VAR} patterns in environment variable values"""
    if isinstance(value, str) and "${" in value:
        # Substituir ${DIVISOR} e outras variáveis
        for key in os.environ:
            placeholder = f"${{{key}}}"
            if placeholder in value:
                value = value.replace(placeholder, os.environ[key])
    return value


class Settings(BaseSettings):
    """Configurações do Make-Video Service"""
    
    # Service Info
    service_name: str = "make-video"
    version: str = "1.0.0"
    
    # Server Configuration
    port: int = int(expand_env_vars(os.getenv("PORT", "8005")))
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Redis Configuration
    redis_url: str = expand_env_vars(os.getenv("REDIS_URL", "redis://localhost:6379/5"))
    cache_ttl_hours: int = int(os.getenv("CACHE_TTL_HOURS", "24"))
    max_cache_size_gb: int = int(os.getenv("MAX_CACHE_SIZE_GB", "50"))
    
    # Microservices URLs
    youtube_search_url: str = os.getenv("YOUTUBE_SEARCH_URL", "https://ytsearch.loadstask.com")
    video_downloader_url: str = os.getenv("VIDEO_DOWNLOADER_URL", "https://ytdownloader.loadstask.com")
    audio_transcriber_url: str = os.getenv("AUDIO_TRANSCRIBER_URL", "https://yttranscriber.loadstask.com")
    
    # Storage Paths - Nova Estrutura (data/raw → data/transform → data/validate → data/approved)
    audio_upload_dir: str = os.getenv("AUDIO_UPLOAD_DIR", "./data/raw/audio")
    shorts_cache_dir: str = os.getenv("SHORTS_CACHE_DIR", "./data/raw/shorts")
    transform_dir: str = os.getenv("TRANSFORM_DIR", "./data/transform/videos")
    validate_dir: str = os.getenv("VALIDATE_DIR", "./data/validate")
    approved_dir: str = os.getenv("APPROVED_DIR", "./data/approved/videos")
    output_dir: str = os.getenv("OUTPUT_DIR", "./data/approved/output")
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_dir: str = os.getenv("LOG_DIR", "./logs")
    log_format: str = os.getenv("LOG_FORMAT", "json")
    
    # Video Processing
    default_aspect_ratio: str = os.getenv("DEFAULT_ASPECT_RATIO", "9:16")
    default_crop_position: str = os.getenv("DEFAULT_CROP_POSITION", "center")
    default_video_quality: str = os.getenv("DEFAULT_VIDEO_QUALITY", "fast")
    
    # Cleanup Settings
    cleanup_temp_after_hours: int = int(os.getenv("CLEANUP_TEMP_AFTER_HOURS", "1"))
    cleanup_output_after_hours: int = int(os.getenv("CLEANUP_OUTPUT_AFTER_HOURS", "24"))
    cleanup_shorts_cache_after_days: int = int(os.getenv("CLEANUP_SHORTS_CACHE_AFTER_DAYS", "30"))
    
    # Video Compatibility Settings
    target_video_height: int = int(os.getenv("TARGET_VIDEO_HEIGHT", "720"))
    target_video_width: int = int(os.getenv("TARGET_VIDEO_WIDTH", "1280"))
    target_video_fps: float = float(os.getenv("TARGET_VIDEO_FPS", "30.0"))
    target_video_codec: str = os.getenv("TARGET_VIDEO_CODEC", "h264")
    
    # SQLite Blacklist (permanente) - DEPRECATED
    sqlite_db_path: str = os.getenv("SQLITE_DB_PATH", "./data/raw/shorts/blacklist.db")
    
    # Video Status Store (novo sistema: approved + rejected)
    video_status_db_path: str = os.getenv("VIDEO_STATUS_DB_PATH", "./data/database/video_status.db")
    
    # Subtitle Settings
    subtitle_font_size: int = int(os.getenv("SUBTITLE_FONT_SIZE", "22"))
    subtitle_font_name: str = os.getenv("SUBTITLE_FONT_NAME", "Arial Black")
    subtitle_color: str = os.getenv("SUBTITLE_COLOR", "&H00FFFF&")
    subtitle_outline_color: str = os.getenv("SUBTITLE_OUTLINE_COLOR", "&H000000&")
    subtitle_outline: int = int(os.getenv("SUBTITLE_OUTLINE", "2"))
    subtitle_alignment: int = int(os.getenv("SUBTITLE_ALIGNMENT", "10"))
    subtitle_margin_v: int = int(os.getenv("SUBTITLE_MARGIN_V", "280"))
    words_per_caption: int = int(os.getenv("WORDS_PER_CAPTION", "1"))  # ✅ 1 palavra = sincronização perfeita
    
    # OCR Detection Settings
    ocr_confidence_threshold: float = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.50"))  # Equilibrado + densidade
    ocr_frames_per_second: int = int(os.getenv("OCR_FRAMES_PER_SECOND", "3"))  # Frames analisados por segundo
    ocr_max_frames: int = int(os.getenv("OCR_MAX_FRAMES", "240"))  # Limite máximo para evitar OOM
    
    # TRSD (Temporal Region Subtitle Detector) Settings - Sprint 01
    trsd_enabled: bool = os.getenv("TRSD_ENABLED", "false").lower() == "true"
    trsd_downscale_width: int = int(os.getenv("TRSD_DOWNSCALE_WIDTH", "640"))
    trsd_min_text_length: int = int(os.getenv("TRSD_MIN_TEXT_LENGTH", "2"))
    trsd_min_confidence: float = float(os.getenv("TRSD_MIN_CONFIDENCE", "0.50"))
    trsd_min_alpha_ratio: float = float(os.getenv("TRSD_MIN_ALPHA_RATIO", "0.60"))
    trsd_line_y_tolerance: int = int(os.getenv("TRSD_LINE_Y_TOLERANCE", "10"))
    trsd_line_x_gap: int = int(os.getenv("TRSD_LINE_X_GAP", "50"))
    
    # TRSD Tracking Settings - Sprint 02
    trsd_track_iou_threshold: float = float(os.getenv("TRSD_TRACK_IOU_THRESHOLD", "0.30"))
    trsd_track_max_distance: int = int(os.getenv("TRSD_TRACK_MAX_DISTANCE", "50"))
    
    # TRSD Classification Settings - Sprint 03
    trsd_ignore_static_text: bool = os.getenv("TRSD_IGNORE_STATIC_TEXT", "true").lower() == "true"
    trsd_static_min_presence: float = float(os.getenv("TRSD_STATIC_MIN_PRESENCE", "0.85"))
    trsd_static_max_change: float = float(os.getenv("TRSD_STATIC_MAX_CHANGE", "0.10"))
    trsd_subtitle_min_change_rate: float = float(os.getenv("TRSD_SUBTITLE_MIN_CHANGE_RATE", "0.25"))
    trsd_screencast_min_detections: int = int(os.getenv("TRSD_SCREENCAST_MIN_DETECTIONS", "10"))
    
    # TRSD Telemetry Settings - Sprint 07
    trsd_save_detection_events: bool = os.getenv("TRSD_SAVE_DETECTION_EVENTS", "false").lower() == "true"
    trsd_save_debug_artifacts: bool = os.getenv("TRSD_SAVE_DEBUG_ARTIFACTS", "false").lower() == "true"
    
    # VAD (Voice Activity Detection) Settings
    vad_threshold: float = float(os.getenv("VAD_THRESHOLD", "0.5"))
    vad_model: str = os.getenv("VAD_MODEL", "webrtc")  # webrtc ou silero
    
    # FFmpeg Encoding Settings
    ffmpeg_video_codec: str = os.getenv("FFMPEG_VIDEO_CODEC", "libx264")
    ffmpeg_audio_codec: str = os.getenv("FFMPEG_AUDIO_CODEC", "aac")
    ffmpeg_preset: str = os.getenv("FFMPEG_PRESET", "fast")  # ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
    ffmpeg_crf: int = int(os.getenv("FFMPEG_CRF", "23"))  # 0 (lossless) a 51 (péssima)
    
    # Video Trimming Settings - Sprint 09
    video_trim_padding_ms: int = int(os.getenv("VIDEO_TRIM_PADDING_MS", "1000"))  # Padding após áudio (milissegundos)
    
    # Celery Worker Settings
    celery_worker_concurrency: int = int(os.getenv("CELERY_WORKER_CONCURRENCY", "4"))
    celery_worker_prefetch_multiplier: int = int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1"))
    celery_task_time_limit: int = int(os.getenv("CELERY_TASK_TIME_LIMIT", "3600"))  # segundos
    
    # API Timeouts
    api_timeout: int = int(os.getenv("API_TIMEOUT", "120"))
    download_poll_interval: int = int(os.getenv("DOWNLOAD_POLL_INTERVAL", "3"))
    download_max_polls: int = int(os.getenv("DOWNLOAD_MAX_POLLS", "40"))
    transcribe_poll_interval: int = int(os.getenv("TRANSCRIBE_POLL_INTERVAL", "5"))
    transcribe_max_polls: int = int(os.getenv("TRANSCRIBE_MAX_POLLS", "240"))
    
    # Video Fetch Settings
    max_fetch_rounds: int = int(os.getenv("MAX_FETCH_ROUNDS", "10"))  # Rodadas de busca de shorts (R1=1x, R2=2x, ..., R10=10x)
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"


# Global settings instance (singleton pattern)
_settings: Settings = None
_settings_dict: Dict[str, Any] = None


def get_settings() -> Dict[str, Any]:
    """Retorna configurações como dicionário (compatível com padrão)
    
    Implementa singleton: retorna sempre o mesmo dict para eficiência
    e consistência. O dict é gerado uma vez na primeira chamada.
    """
    global _settings, _settings_dict
    
    # Criar Settings singleton se necessário
    if _settings is None:
        _settings = Settings()
    
    # Criar dict singleton se necessário
    if _settings_dict is None:
        _settings_dict = {
            "service_name": _settings.service_name,
            "version": _settings.version,
            "port": _settings.port,
            "debug": _settings.debug,
            "redis_url": _settings.redis_url,
            "cache_ttl_hours": _settings.cache_ttl_hours,
            "max_cache_size_gb": _settings.max_cache_size_gb,
            "youtube_search_url": _settings.youtube_search_url,
            "video_downloader_url": _settings.video_downloader_url,
            "audio_transcriber_url": _settings.audio_transcriber_url,
            "audio_upload_dir": _settings.audio_upload_dir,
            "shorts_cache_dir": _settings.shorts_cache_dir,
            "transform_dir": _settings.transform_dir,
            "validate_dir": _settings.validate_dir,
            "approved_dir": _settings.approved_dir,
            "output_dir": _settings.output_dir,
            "log_level": _settings.log_level,
            "logs_dir": _settings.log_dir,  # Adicionar logs_dir também
            "log_dir": _settings.log_dir,
            "log_format": _settings.log_format,
            "default_aspect_ratio": _settings.default_aspect_ratio,
            "default_crop_position": _settings.default_crop_position,
            "default_video_quality": _settings.default_video_quality,
            "cleanup_temp_after_hours": _settings.cleanup_temp_after_hours,
            "cleanup_output_after_hours": _settings.cleanup_output_after_hours,
            "cleanup_shorts_cache_after_days": _settings.cleanup_shorts_cache_after_days,
            "target_video_height": _settings.target_video_height,
            "target_video_width": _settings.target_video_width,
            "target_video_fps": _settings.target_video_fps,
            "target_video_codec": _settings.target_video_codec,
            "sqlite_db_path": _settings.sqlite_db_path,  # DEPRECATED
            "video_status_db_path": _settings.video_status_db_path,  # NEW
            "subtitle_font_size": _settings.subtitle_font_size,
            "subtitle_font_name": _settings.subtitle_font_name,
            "subtitle_color": _settings.subtitle_color,
            "subtitle_outline_color": _settings.subtitle_outline_color,
            "subtitle_outline": _settings.subtitle_outline,
            "subtitle_alignment": _settings.subtitle_alignment,
            "subtitle_margin_v": _settings.subtitle_margin_v,
            "words_per_caption": _settings.words_per_caption,
            "ocr_confidence_threshold": _settings.ocr_confidence_threshold,
            "ocr_frames_per_second": _settings.ocr_frames_per_second,
            "ocr_max_frames": _settings.ocr_max_frames,
            "vad_threshold": _settings.vad_threshold,
            "vad_model": _settings.vad_model,
            "ffmpeg_video_codec": _settings.ffmpeg_video_codec,
            "ffmpeg_audio_codec": _settings.ffmpeg_audio_codec,
            "ffmpeg_preset": _settings.ffmpeg_preset,
            "ffmpeg_crf": _settings.ffmpeg_crf,
            "celery_worker_concurrency": _settings.celery_worker_concurrency,
            "celery_worker_prefetch_multiplier": _settings.celery_worker_prefetch_multiplier,
            "celery_task_time_limit": _settings.celery_task_time_limit,
            "max_fetch_rounds": _settings.max_fetch_rounds,
            "video_trim_padding_ms": _settings.video_trim_padding_ms,
        }
    
    return _settings_dict


def ensure_directories():
    """Cria diretórios necessários se não existirem"""
    settings = get_settings()
    
    dirs = [
        settings["audio_upload_dir"],
        settings["shorts_cache_dir"],
        settings["output_dir"],
        settings["log_dir"],
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
