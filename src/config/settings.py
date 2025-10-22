"""
Settings module - Configurações centralizadas da aplicação usando Pydantic Settings.
Segue o princípio de Single Responsibility (SOLID).
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator


class Settings(BaseSettings):
    """Configurações da aplicação."""
    
    # Application
    app_name: str = Field(default="Whisper Transcription API", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    app_environment: str = Field(default="production", alias="APP_ENVIRONMENT")
    
    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    
    # Whisper
    whisper_model: str = Field(default="base", alias="WHISPER_MODEL")
    whisper_device: str = Field(default="cpu", alias="WHISPER_DEVICE")
    whisper_language: str = Field(default="auto", alias="WHISPER_LANGUAGE")
    
    # Parallel Transcription (Experimental)
    enable_parallel_transcription: bool = Field(default=False, alias="ENABLE_PARALLEL_TRANSCRIPTION")
    parallel_workers: int = Field(default=4, alias="PARALLEL_WORKERS")
    parallel_chunk_duration: int = Field(default=120, alias="PARALLEL_CHUNK_DURATION")
    
    # Audio Normalization (Advanced)
    enable_audio_volume_normalization: bool = Field(default=False, alias="ENABLE_AUDIO_VOLUME_NORMALIZATION")
    enable_audio_noise_reduction: bool = Field(default=False, alias="ENABLE_AUDIO_NOISE_REDUCTION")
    
    # YouTube
    youtube_format: str = Field(default="worstaudio", alias="YOUTUBE_FORMAT")
    max_video_size_mb: int = Field(default=1500, alias="MAX_VIDEO_SIZE_MB")
    max_video_duration_seconds: int = Field(default=10800, alias="MAX_VIDEO_DURATION_SECONDS")  # 3 horas
    download_timeout: int = Field(default=900, alias="DOWNLOAD_TIMEOUT")  # 15 minutos
    
    # Storage
    temp_dir: str = Field(default="./temp", alias="TEMP_DIR")
    cleanup_on_startup: bool = Field(default=True, alias="CLEANUP_ON_STARTUP")
    cleanup_after_processing: bool = Field(default=True, alias="CLEANUP_AFTER_PROCESSING")
    max_temp_age_hours: int = Field(default=24, alias="MAX_TEMP_AGE_HOURS")
    
    # API
    max_concurrent_requests: int = Field(default=3, alias="MAX_CONCURRENT_REQUESTS")
    request_timeout: int = Field(default=3600, alias="REQUEST_TIMEOUT")  # 1 hora
    enable_cors: bool = Field(default=True, alias="ENABLE_CORS")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")
    log_file: str = Field(default="./logs/app.log", alias="LOG_FILE")
    
    # Performance
    workers: int = Field(default=1, alias="WORKERS")
    
    # Cache (NOVO - v2.0)
    enable_transcription_cache: bool = Field(default=True, alias="ENABLE_TRANSCRIPTION_CACHE")
    cache_max_size: int = Field(default=100, alias="CACHE_MAX_SIZE")
    cache_ttl_hours: int = Field(default=24, alias="CACHE_TTL_HOURS")
    
    # Model Cache (NOVO - v2.0)
    whisper_model_cache_timeout_minutes: int = Field(default=30, alias="MODEL_CACHE_TIMEOUT_MINUTES")
    
    # FFmpeg Optimization (NOVO - v2.0)
    enable_ffmpeg_hw_accel: bool = Field(default=True, alias="ENABLE_FFMPEG_HW_ACCEL")
    
    # File Cleanup (NOVO - v2.0)
    enable_periodic_cleanup: bool = Field(default=True, alias="ENABLE_PERIODIC_CLEANUP")
    cleanup_interval_minutes: int = Field(default=30, alias="CLEANUP_INTERVAL_MINUTES")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=()  # Desabilita proteção de namespace 'model_'
    )
    
    @validator("whisper_model")
    def validate_whisper_model(cls, v: str) -> str:
        """Valida o modelo Whisper."""
        valid_models = ["tiny", "base", "small", "medium", "large", "turbo"]
        if v not in valid_models:
            raise ValueError(f"Model must be one of {valid_models}")
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        """Valida o nível de log."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v
    
    def get_cors_origins(self) -> List[str]:
        """Retorna lista de origens CORS permitidas."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]


# Instância global de configurações
settings = Settings()
