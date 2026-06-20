"""
Configuration module — loads settings from environment variables.
Uses pydantic_settings for type validation + lru_cache singleton.
"""
from functools import lru_cache
from typing import Any, Optional

from pydantic import Field, field_validator

from common.config_utils.base_settings import BaseServiceSettings


class ServiceSettings(BaseServiceSettings):
    """Audio Normalization Service settings — validated & typed."""

    app_name: str = "Audio Normalization Service"
    app_version: str = "2.0.0"
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8003
    max_file_size_mb: int = 2048
    max_duration_minutes: int = 120

    # Celery
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None
    celery_task_time_limit: int = Field(default=1800, env="CELERY_TASK_TIME_LIMIT")
    celery_task_soft_time_limit: int = Field(default=1500, env="CELERY_TASK_SOFT_TIME_LIMIT")

    # Processing
    processing_max_concurrent_jobs: int = Field(default=3, env="PROCESSING__MAX_CONCURRENT_JOBS")
    processing_job_timeout_minutes: int = Field(default=30, env="PROCESSING__JOB_TIMEOUT_MINUTES")

    # Audio chunking
    audio_enable_chunking: bool = Field(default=True, env="AUDIO_ENABLE_CHUNKING")
    audio_chunk_size_mb: int = Field(default=30, env="AUDIO_CHUNK_SIZE_MB")
    audio_chunk_duration_sec: int = Field(default=60, env="AUDIO_CHUNK_DURATION_SEC")
    audio_chunk_overlap_sec: int = Field(default=1, env="AUDIO_CHUNK_OVERLAP_SEC")

    # Noise reduction
    noise_reduction_max_duration_sec: int = Field(default=300, env="NOISE_REDUCTION_MAX_DURATION_SEC")
    noise_reduction_sample_rate: int = Field(default=22050, env="NOISE_REDUCTION_SAMPLE_RATE")
    noise_reduction_chunk_size_sec: int = Field(default=30, env="NOISE_REDUCTION_CHUNK_SIZE_SEC")

    # Vocal isolation
    vocal_isolation_max_duration_sec: int = Field(default=180, env="VOCAL_ISOLATION_MAX_DURATION_SEC")

    # Extraction
    extraction_timeout_sec: int = Field(default=300, env="EXTRACTION_TIMEOUT_SEC")

    # Timeouts
    async_timeout_seconds: int = Field(default=900, env="ASYNC_TIMEOUT_SECONDS")
    job_processing_timeout_seconds: int = Field(default=3600, env="JOB_PROCESSING_TIMEOUT_SECONDS")

    # Ffmpeg
    ffmpeg_threads: int = Field(default=0, env="FFMPEG_THREADS")
    ffmpeg_preset: str = Field(default="medium", env="FFMPEG_PRESET")
    ffmpeg_audio_codec: str = Field(default="libopus", env="FFMPEG_AUDIO_CODEC")
    ffmpeg_audio_bitrate: str = Field(default="128k", env="FFMPEG_AUDIO_BITRATE")

    # Directories
    upload_dir: str = "./data/uploads"
    processed_dir: str = "./data/processed"
    log_dir: str = "./data/logs"
    backup_dir: str = "./backup"

    @field_validator("port")
    @classmethod
    def port_must_be_valid(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"PORT must be 1-65535, got {v}")
        return v

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key, None)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


_core = ServiceSettings()


@lru_cache(maxsize=1)
def get_settings() -> ServiceSettings:
    """Returns the typed Pydantic settings instance."""
    return _core


def get_service_config() -> dict:
    """Retorna configuração específica para os serviços."""
    s = get_settings()
    return {
        'max_file_size_mb': s.max_file_size_mb,
        'max_duration_minutes': s.max_duration_minutes,
        'temp_dir': s.temp_dir,
        'processed_dir': s.processed_dir,
        'noise_reduction': {
            'max_duration_sec': s.noise_reduction_max_duration_sec,
            'sample_rate': s.noise_reduction_sample_rate,
            'chunk_size_sec': s.noise_reduction_chunk_size_sec,
        },
        'highpass_filter': {
            'cutoff_hz': 80,
            'order': 5,
        },
        'ffmpeg': {
            'threads': s.ffmpeg_threads,
            'preset': s.ffmpeg_preset,
            'audio_codec': s.ffmpeg_audio_codec,
            'audio_bitrate': s.ffmpeg_audio_bitrate,
        },
        'extraction_timeout_sec': s.extraction_timeout_sec,
    }


