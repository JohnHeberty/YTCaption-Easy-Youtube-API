"""
Configuration module — loads settings from environment variables.
Uses pydantic_settings for type validation + lru_cache singleton.
"""
import os
from functools import lru_cache
from typing import Any, Dict

from pydantic import field_validator
from pydantic_settings import BaseSettings


class _CoreSettings(BaseSettings):
    """Validates critical typed settings at startup (fail-fast)."""

    app_name: str = "Audio Normalization Service"
    version: str = "2.0.0"
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8002
    redis_url: str = "redis://localhost:6379/0"
    max_file_size_mb: int = 2048
    max_duration_minutes: int = 120
    log_level: str = "INFO"

    @field_validator("port")
    @classmethod
    def port_must_be_valid(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"PORT must be 1-65535, got {v}")
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Validate critical settings at import time — raises ValidationError on bad env vars
_core = _CoreSettings()


@lru_cache(maxsize=1)
def get_settings() -> Dict[str, Any]:
    """
    Returns all service settings from environment variables.
    Result is cached (singleton) — env changes after first call are ignored.
    Settings organised by category for easy maintenance.
    """
    return {
        # ===== APLICAÇÃO =====
        'app_name': os.getenv('APP_NAME', 'Audio Normalization Service'),
        'version': os.getenv('VERSION', '2.0.0'),
        'environment': os.getenv('ENVIRONMENT', 'development'),
        'debug': os.getenv('DEBUG', 'false').lower() == 'true',
        'host': os.getenv('HOST', '0.0.0.0'),
        'port': int(os.getenv('PORT', '8002')),
        
        # ===== REDIS =====
        'redis_url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        
        # ===== CELERY =====
        'celery': {
            'broker_url': os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0')),
            'result_backend': os.getenv('CELERY_RESULT_BACKEND', os.getenv('REDIS_URL', 'redis://localhost:6379/0')),
            'task_serializer': os.getenv('CELERY_TASK_SERIALIZER', 'json'),
            'result_serializer': os.getenv('CELERY_RESULT_SERIALIZER', 'json'),
            'accept_content': os.getenv('CELERY_ACCEPT_CONTENT', 'json').split(','),
            'timezone': os.getenv('CELERY_TIMEZONE', 'UTC'),
            'enable_utc': os.getenv('CELERY_ENABLE_UTC', 'true').lower() == 'true',
            'task_track_started': os.getenv('CELERY_TASK_TRACK_STARTED', 'true').lower() == 'true',
            'task_time_limit': int(os.getenv('CELERY_TASK_TIME_LIMIT', '1800')),
            'task_soft_time_limit': int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', '1500')),
            'worker_prefetch_multiplier': int(os.getenv('CELERY_WORKER_PREFETCH_MULTIPLIER', '1')),
            'worker_max_tasks_per_child': int(os.getenv('CELERY_WORKER_MAX_TASKS_PER_CHILD', '100')),
        },
        
        # ===== CACHE =====
        'cache_ttl_hours': int(os.getenv('CACHE__TTL_HOURS', '24')),
        'cache_cleanup_interval_minutes': int(os.getenv('CACHE__CLEANUP_INTERVAL_MINUTES', '30')),
        'cache_max_size_mb': int(os.getenv('CACHE__MAX_CACHE_SIZE_MB', '1024')),
        
        # ===== PROCESSAMENTO - LIMITES =====
        'max_file_size_mb': int(os.getenv('MAX_FILE_SIZE_MB', os.getenv('PROCESSING__MAX_FILE_SIZE_MB', '2048'))),
        'max_duration_minutes': int(os.getenv('MAX_DURATION_MINUTES', os.getenv('PROCESSING__MAX_DURATION_MINUTES', '120'))),
        'max_concurrent_jobs': int(os.getenv('PROCESSING__MAX_CONCURRENT_JOBS', '3')),
        'job_timeout_minutes': int(os.getenv('PROCESSING__JOB_TIMEOUT_MINUTES', '30')),
        
        # ===== PROCESSAMENTO - CHUNKS =====
        'audio_chunking': {
            'enabled': os.getenv('AUDIO_ENABLE_CHUNKING', 'true').lower() == 'true',
            'chunk_size_mb': int(os.getenv('AUDIO_CHUNK_SIZE_MB', '30')),
            'chunk_duration_sec': int(os.getenv('AUDIO_CHUNK_DURATION_SEC', '60')),
            'chunk_overlap_sec': int(os.getenv('AUDIO_CHUNK_OVERLAP_SEC', '1')),
            'streaming_threshold_mb': int(os.getenv('AUDIO_STREAMING_THRESHOLD_MB', '50')),
        },
        
        # ===== PROCESSAMENTO - OPERAÇÕES =====
        'noise_reduction': {
            'max_duration_sec': int(os.getenv('NOISE_REDUCTION_MAX_DURATION_SEC', '300')),
            'sample_rate': int(os.getenv('NOISE_REDUCTION_SAMPLE_RATE', '22050')),
            'chunk_size_sec': int(os.getenv('NOISE_REDUCTION_CHUNK_SIZE_SEC', '30')),
        },
        
        'vocal_isolation': {
            'max_duration_sec': int(os.getenv('VOCAL_ISOLATION_MAX_DURATION_SEC', '180')),
            'sample_rate': int(os.getenv('VOCAL_ISOLATION_SAMPLE_RATE', '44100')),
            'device': os.getenv('VOCAL_ISOLATION_DEVICE', 'cpu'),
        },
        
        'highpass_filter': {
            'cutoff_hz': int(os.getenv('HIGHPASS_FILTER_CUTOFF_HZ', '80')),
            'order': int(os.getenv('HIGHPASS_FILTER_ORDER', '5')),
        },
        
        # ===== EXTRACTION =====
        'extraction_timeout_sec': int(os.getenv('EXTRACTION_TIMEOUT_SEC', '300')),
        
        # ===== TIMEOUTS =====
        'timeouts': {
            'async_timeout_sec': int(os.getenv('ASYNC_TIMEOUT_SECONDS', '900')),
            'job_processing_timeout_sec': int(os.getenv('JOB_PROCESSING_TIMEOUT_SECONDS', '3600')),
            'poll_interval_sec': int(os.getenv('POLL_INTERVAL_SECONDS', '2')),
            'job_heartbeat_interval_sec': int(os.getenv('JOB_HEARTBEAT_INTERVAL_SEC', '30')),
            'job_orphan_timeout_minutes': int(os.getenv('JOB_ORPHAN_TIMEOUT_MINUTES', '15')),
        },
        
        # ===== FFMPEG =====
        'ffmpeg': {
            'threads': int(os.getenv('FFMPEG_THREADS', '0')),
            'preset': os.getenv('FFMPEG_PRESET', 'medium'),
            'audio_codec': os.getenv('FFMPEG_AUDIO_CODEC', 'libopus'),
            'audio_bitrate': os.getenv('FFMPEG_AUDIO_BITRATE', '128k'),
        },
        
        # ===== DIRETÓRIOS =====
        'upload_dir': os.getenv('UPLOAD_DIR', './uploads'),
        'processed_dir': os.getenv('PROCESSED_DIR', './processed'),
        'temp_dir': os.getenv('TEMP_DIR', './temp'),
        'log_dir': os.getenv('LOG_DIR', './logs'),
        'backup_dir': os.getenv('BACKUP_DIR', './backup'),
        
        # ===== LOGGING =====
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'log_format': os.getenv('LOG_FORMAT', 'json'),
        'log_rotation': os.getenv('LOG_ROTATION', '1 day'),
        'log_retention': os.getenv('LOG_RETENTION', '30 days')
    }


def get_service_config() -> Dict[str, Any]:
    """
    Retorna configuração específica para os serviços (SOLID)
    """
    settings = get_settings()
    
    return {
        'max_file_size_mb': settings['max_file_size_mb'],
        'max_duration_minutes': settings['max_duration_minutes'],
        'temp_dir': settings['temp_dir'],
        'processed_dir': settings['processed_dir'],
        'noise_reduction': settings['noise_reduction'],
        'highpass_filter': settings['highpass_filter'],
        'ffmpeg': settings['ffmpeg'],
        'extraction_timeout_sec': settings['extraction_timeout_sec'],
    }


