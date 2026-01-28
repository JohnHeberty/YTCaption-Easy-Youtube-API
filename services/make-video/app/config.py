import os
from pathlib import Path
from typing import Dict, Any
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings(BaseSettings):
    """Configurações do Make-Video Service"""
    
    # Service Info
    service_name: str = "make-video"
    version: str = "1.0.0"
    
    # Server Configuration
    port: int = int(os.getenv("PORT", "8004"))
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Redis Configuration
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    cache_ttl_hours: int = int(os.getenv("CACHE_TTL_HOURS", "24"))
    max_cache_size_gb: int = int(os.getenv("MAX_CACHE_SIZE_GB", "50"))
    
    # Microservices URLs
    youtube_search_url: str = os.getenv("YOUTUBE_SEARCH_URL", "https://ytsearch.loadstask.com")
    video_downloader_url: str = os.getenv("VIDEO_DOWNLOADER_URL", "https://ytdownloader.loadstask.com")
    audio_transcriber_url: str = os.getenv("AUDIO_TRANSCRIBER_URL", "https://yttranscriber.loadstask.com")
    
    # Storage Paths
    audio_upload_dir: str = os.getenv("AUDIO_UPLOAD_DIR", "./storage/audio_uploads")
    shorts_cache_dir: str = os.getenv("SHORTS_CACHE_DIR", "./storage/shorts_cache")
    temp_dir: str = os.getenv("TEMP_DIR", "./storage/temp")
    output_dir: str = os.getenv("OUTPUT_DIR", "./storage/output_videos")
    
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
    
    # Subtitle Settings
    subtitle_font_size: int = int(os.getenv("SUBTITLE_FONT_SIZE", "22"))
    subtitle_font_name: str = os.getenv("SUBTITLE_FONT_NAME", "Arial Black")
    subtitle_color: str = os.getenv("SUBTITLE_COLOR", "&H00FFFF&")
    subtitle_outline_color: str = os.getenv("SUBTITLE_OUTLINE_COLOR", "&H000000&")
    subtitle_outline: int = int(os.getenv("SUBTITLE_OUTLINE", "2"))
    subtitle_alignment: int = int(os.getenv("SUBTITLE_ALIGNMENT", "10"))
    subtitle_margin_v: int = int(os.getenv("SUBTITLE_MARGIN_V", "280"))
    words_per_caption: int = int(os.getenv("WORDS_PER_CAPTION", "2"))
    
    # API Timeouts
    api_timeout: int = int(os.getenv("API_TIMEOUT", "120"))
    download_poll_interval: int = int(os.getenv("DOWNLOAD_POLL_INTERVAL", "3"))
    download_max_polls: int = int(os.getenv("DOWNLOAD_MAX_POLLS", "40"))
    transcribe_poll_interval: int = int(os.getenv("TRANSCRIBE_POLL_INTERVAL", "5"))
    transcribe_max_polls: int = int(os.getenv("TRANSCRIBE_MAX_POLLS", "240"))
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"


# Global settings instance
_settings: Settings = None


def get_settings() -> Dict[str, Any]:
    """Retorna configurações como dicionário (compatível com padrão)"""
    global _settings
    if _settings is None:
        _settings = Settings()
    
    return {
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
        "temp_dir": _settings.temp_dir,
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
        "subtitle_font_size": _settings.subtitle_font_size,
        "subtitle_font_name": _settings.subtitle_font_name,
        "subtitle_color": _settings.subtitle_color,
        "subtitle_outline_color": _settings.subtitle_outline_color,
        "subtitle_outline": _settings.subtitle_outline,
        "subtitle_alignment": _settings.subtitle_alignment,
        "subtitle_margin_v": _settings.subtitle_margin_v,
        "words_per_caption": _settings.words_per_caption,
    }


def ensure_directories():
    """Cria diretórios necessários se não existirem"""
    settings = get_settings()
    
    dirs = [
        settings["audio_upload_dir"],
        settings["shorts_cache_dir"],
        settings["temp_dir"],
        settings["output_dir"],
        settings["log_dir"],
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
