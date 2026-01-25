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
    youtube_search_url: str = os.getenv("YOUTUBE_SEARCH_URL", "http://localhost:8003")
    video_downloader_url: str = os.getenv("VIDEO_DOWNLOADER_URL", "http://localhost:8002")
    audio_transcriber_url: str = os.getenv("AUDIO_TRANSCRIBER_URL", "http://localhost:8005")
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = False


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
        "log_dir": _settings.log_dir,
        "log_format": _settings.log_format,
        "default_aspect_ratio": _settings.default_aspect_ratio,
        "default_crop_position": _settings.default_crop_position,
        "default_video_quality": _settings.default_video_quality,
        "cleanup_temp_after_hours": _settings.cleanup_temp_after_hours,
        "cleanup_output_after_hours": _settings.cleanup_output_after_hours,
        "cleanup_shorts_cache_after_days": _settings.cleanup_shorts_cache_after_days,
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
