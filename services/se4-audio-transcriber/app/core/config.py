from functools import lru_cache
from typing import Any, Dict, Iterator, List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class CoreSettings(BaseSettings):
    """Single source of truth for all service configuration.

    Replaces the old untyped get_settings() dict with a fully typed Pydantic model.
    All ~42 keys from both systems are consolidated here.  Backward-compatible:
    behaves like a dict (supports .get(), bracket access, iteration).
    """

    # ===== APLICAÇÃO =====
    app_name: str = "Audio Transcription Service"
    version: str = "2.0.0"
    environment: str = "development"
    debug: bool = False

    # ===== SERVIDOR =====
    host: str = "0.0.0.0"
    port: int = 8002
    workers: int = Field(1, ge=1)

    # ===== REDIS =====
    redis_url: str = "redis://localhost:6379/0"

    # ===== CELERY =====
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None
    celery_task_time_limit: int = 3600
    celery_task_soft_time_limit: int = 3300

    @model_validator(mode="after")
    def _default_celery_from_redis(self) -> "CoreSettings":
        if self.celery_broker_url is None:
            self.celery_broker_url = self.redis_url
        if self.celery_result_backend is None:
            self.celery_result_backend = self.redis_url
        return self

    # ===== CACHE =====
    cache_ttl_hours: int = Field(24, ge=1)
    cache_cleanup_interval_minutes: int = Field(30, ge=1)
    cache_max_size_mb: int = Field(2048, ge=1)

    # ===== LIMITES DE ARQUIVO =====
    max_file_size_mb: int = Field(500, ge=1)
    max_duration_minutes: int = Field(120, ge=1)

    # ===== WHISPER - MODELO =====
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_download_root: str = "./data/models"

    # ===== WHISPER - CHUNKS (ACELERAÇÃO) =====
    enable_chunking: bool = True
    chunk_length_seconds: int = Field(30, ge=1)
    chunk_overlap_seconds: float = Field(1.0, ge=0.0)
    whisper_min_duration_for_chunks: int = Field(300, ge=0)

    # ===== WHISPER - OTIMIZAÇÕES =====
    whisper_fp16: bool = False
    whisper_beam_size: int = Field(5, ge=1)
    whisper_best_of: int = Field(5, ge=1)
    whisper_temperature: float = Field(0.0, ge=0.0, le=1.0)

    # ===== DIRETÓRIOS =====
    upload_dir: str = "./data/uploads"
    transcription_dir: str = "./data/transcriptions"
    models_dir: str = "./data/models"
    temp_dir: str = "./data/temp"
    log_dir: str = "./data/logs"

    # ===== LOGGING =====
    log_level: str = "INFO"
    log_format: str = "json"
    log_rotation: str = "1 day"
    log_retention: str = "30 days"

    # ===== TIMEOUTS =====
    async_timeout_seconds: int = Field(1800, ge=1)
    job_processing_timeout_seconds: int = Field(3600, ge=1)
    poll_interval_seconds: int = Field(2, ge=1)

    # ===== FFMPEG =====
    ffmpeg_threads: int = 0  # 0 = auto
    ffmpeg_audio_codec: str = "pcm_s16le"
    ffmpeg_sample_rate: int = Field(16000, ge=8000)

    @field_validator("port")
    @classmethod
    def _port_range(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"PORT must be 1-65535, got {v}")
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    # Per-field alias: env var WHISPER_DEFAULT_LANGUAGE -> field whisper_language
    whisper_language: str = Field("auto", validation_alias="WHISPER_DEFAULT_LANGUAGE")

    # ---- dict-like protocol so old code that treats settings as a dict still works ----
    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def keys(self):
        return self.model_fields.keys()

    def values(self):
        for k in self.model_fields:
            yield getattr(self, k)

    def items(self):
        for k in self.model_fields:
            yield k, getattr(self, k)

    def __iter__(self) -> Iterator[str]:
        return iter(self.keys())


# Module-level singleton — replaces old _CoreSettings() + get_settings() dual system.
_core = CoreSettings()


def get_core() -> CoreSettings:
    """Return the typed settings singleton."""
    return _core


@lru_cache(maxsize=1)
def get_settings() -> Dict[str, Any]:
    """Backward-compatible wrapper — returns a plain dict from the Pydantic model.

    Existing code that does ``settings['key']`` or ``settings.get('key')`` continues to work.
    New code should prefer ``get_core().key`` for type safety.
    """
    return _core.model_dump()


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


def get_supported_languages() -> List[str]:
    """Retorna lista de linguagens suportadas pelo Whisper"""
    return SUPPORTED_LANGUAGES


def is_language_supported(language: Optional[str]) -> bool:
    """Verifica se uma linguagem é suportada (case-sensitive)"""
    if not isinstance(language, str):
        return False
    return language in SUPPORTED_LANGUAGES


def get_whisper_models() -> List[str]:
    """Retorna lista de modelos Whisper disponíveis"""
    return WHISPER_MODELS
