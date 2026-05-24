import os
from functools import lru_cache
from typing import Any, List

from pydantic import field_validator
from pydantic_settings import BaseSettings


class _CoreSettings(BaseSettings):
    """Validates critical typed settings at startup (fail-fast)."""

    app_name: str = "Audio Transcription Service"
    version: str = "2.0.0"
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8003
    redis_url: str = "redis://localhost:6379/0"
    whisper_model: str = "base"
    whisper_device: str = "cpu"
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

# Linguagens suportadas pelo Whisper
# Fonte: https://github.com/openai/whisper#available-models-and-languages
SUPPORTED_LANGUAGES = [
    "auto",  # Detecção automática
    "en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr", "pl", "ca", "nl", 
    "ar", "sv", "it", "id", "hi", "fi", "vi", "he", "uk", "el", "ms", "cs", "ro", 
    "da", "hu", "ta", "no", "th", "ur", "hr", "bg", "lt", "la", "mi", "ml", "cy", 
    "sk", "te", "fa", "lv", "bn", "sr", "az", "sl", "kn", "et", "mk", "br", "eu", 
    "is", "hy", "ne", "mn", "bs", "kk", "sq", "sw", "gl", "mr", "pa", "si", "km", 
    "sn", "yo", "so", "af", "oc", "ka", "be", "tg", "sd", "gu", "am", "yi", "lo", 
    "uz", "fo", "ht", "ps", "tk", "nn", "mt", "sa", "lb", "my", "bo", "tl", "mg", 
    "as", "tt", "haw", "ln", "ha", "ba", "jw", "su"
]

# Modelos Whisper disponíveis
WHISPER_MODELS = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]

@lru_cache(maxsize=1)
def get_settings() -> dict:
    """Return singleton settings dict (cached). Env changes after first call are ignored."""
    return {
        # ===== APLICAÇÃO =====
        'app_name': os.getenv('APP_NAME', 'Audio Transcription Service'),
        'version': os.getenv('VERSION', '2.0.0'),
        'environment': os.getenv('ENVIRONMENT', 'development'),
        'debug': os.getenv('DEBUG', 'false').lower() == 'true',
        
        # ===== SERVIDOR =====
        'host': os.getenv('HOST', '0.0.0.0'),
        'port': int(os.getenv('PORT', '8002')),
        'workers': int(os.getenv('WORKERS', '1')),
        
        # ===== REDIS =====
        'redis_url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        
        # ===== CELERY =====
        'celery_broker_url': os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0')),
        'celery_result_backend': os.getenv('CELERY_RESULT_BACKEND', os.getenv('REDIS_URL', 'redis://localhost:6379/0')),
        'celery_task_time_limit': int(os.getenv('CELERY_TASK_TIME_LIMIT', '3600')),  # 1 hora
        'celery_task_soft_time_limit': int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', '3300')),  # 55 min
        
        # ===== CACHE =====
        'cache_ttl_hours': int(os.getenv('CACHE_TTL_HOURS', '24')),
        'cache_cleanup_interval_minutes': int(os.getenv('CACHE_CLEANUP_INTERVAL_MINUTES', '30')),
        'cache_max_size_mb': int(os.getenv('CACHE_MAX_SIZE_MB', '2048')),
        
        # ===== LIMITES DE ARQUIVO =====
        'max_file_size_mb': int(os.getenv('MAX_FILE_SIZE_MB', '500')),
        'max_duration_minutes': int(os.getenv('MAX_DURATION_MINUTES', '120')),
        
        # ===== WHISPER - MODELO =====
        'whisper_model': os.getenv('WHISPER_MODEL', 'base'),  # tiny, base, small, medium, large
        'whisper_device': os.getenv('WHISPER_DEVICE', 'cpu'),  # cpu ou cuda
        'whisper_download_root': os.getenv('WHISPER_DOWNLOAD_ROOT', './data/models'),
        'whisper_language': os.getenv('WHISPER_DEFAULT_LANGUAGE', 'auto'),
        
        # ===== WHISPER - CHUNKS (ACELERAÇÃO) =====
        'enable_chunking': os.getenv('WHISPER_ENABLE_CHUNKING', 'true').lower() == 'true',
        'chunk_length_seconds': int(os.getenv('WHISPER_CHUNK_LENGTH_SECONDS', '30')),  # 30s por chunk
        'chunk_overlap_seconds': float(os.getenv('WHISPER_CHUNK_OVERLAP_SECONDS', '1.0')),  # 1s overlap
        'whisper_min_duration_for_chunks': int(os.getenv('WHISPER_MIN_DURATION_FOR_CHUNKS', '300')),  # 5 min
        
        # ===== WHISPER - OTIMIZAÇÕES =====
        'whisper_fp16': os.getenv('WHISPER_FP16', 'false').lower() == 'true',  # Usar FP16 (GPU)
        'whisper_beam_size': int(os.getenv('WHISPER_BEAM_SIZE', '5')),  # Beam search
        'whisper_best_of': int(os.getenv('WHISPER_BEST_OF', '5')),  # Número de candidatos
        'whisper_temperature': float(os.getenv('WHISPER_TEMPERATURE', '0.0')),  # 0.0-1.0
        
        # ===== DIRETÓRIOS =====
        'upload_dir': os.getenv('UPLOAD_DIR', './data/uploads'),
        'transcription_dir': os.getenv('TRANSCRIPTION_DIR', './data/transcriptions'),
        'models_dir': os.getenv('MODELS_DIR', './data/models'),
        'temp_dir': os.getenv('TEMP_DIR', './data/temp'),
        'log_dir': os.getenv('LOG_DIR', './data/logs'),
        
        # ===== LOGGING =====
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'log_format': os.getenv('LOG_FORMAT', 'json'),  # json ou text
        'log_rotation': os.getenv('LOG_ROTATION', '1 day'),
        'log_retention': os.getenv('LOG_RETENTION', '30 days'),
        
        # ===== TIMEOUTS =====
        'async_timeout_seconds': int(os.getenv('ASYNC_TIMEOUT_SECONDS', '1800')),  # 30 min
        'job_processing_timeout_seconds': int(os.getenv('JOB_PROCESSING_TIMEOUT_SECONDS', '3600')),  # 1 hora
        'poll_interval_seconds': int(os.getenv('POLL_INTERVAL_SECONDS', '2')),
        
        # ===== FFMPEG =====
        'ffmpeg_threads': int(os.getenv('FFMPEG_THREADS', '0')),  # 0 = auto
        'ffmpeg_audio_codec': os.getenv('FFMPEG_AUDIO_CODEC', 'pcm_s16le'),
        'ffmpeg_sample_rate': int(os.getenv('FFMPEG_SAMPLE_RATE', '16000')),  # 16kHz ideal para Whisper
    }

def get_supported_languages() -> List[str]:
    """Retorna lista de linguagens suportadas pelo Whisper"""
    return SUPPORTED_LANGUAGES

def is_language_supported(language: str) -> bool:
    """Verifica se uma linguagem é suportada"""
    return language.lower() in [lang.lower() for lang in SUPPORTED_LANGUAGES]

def get_whisper_models() -> List[str]:
    """Retorna lista de modelos Whisper disponíveis"""
    return WHISPER_MODELS
