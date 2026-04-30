"""
Configurações da API Orquestradora usando Pydantic Settings.
Carrega variáveis de ambiente e configurações dos microserviços.
"""
from functools import lru_cache
from typing import Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class OrchestratorSettings(BaseSettings):
    """Configurações do orquestrador via Pydantic Settings."""

    # Application
    app_name: str = Field(default="youtube-caption-orchestrator")
    app_version: str = Field(default="1.0.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)

    # Server
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8080)
    workers: int = Field(default=1)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Cache e TTL
    cache_ttl_hours: int = Field(default=24)
    job_timeout_minutes: int = Field(default=60)

    # Limitações de recursos
    max_file_size_mb: int = Field(default=500)

    # Logging
    log_level: str = Field(default="INFO")
    log_dir: str = Field(default="./logs")

    # Microserviços URLs - required but with None default for validation
    video_downloader_url: Optional[str] = Field(
        default=None,
        description="URL do serviço video-downloader (http://host:port)"
    )
    audio_normalization_url: Optional[str] = Field(
        default=None,
        description="URL do serviço audio-normalization (http://host:port)"
    )
    audio_transcriber_url: Optional[str] = Field(
        default=None,
        description="URL do serviço audio-transcriber (http://host:port)"
    )

    # Timeouts dos microserviços (segundos)
    video_downloader_timeout: int = Field(default=300)
    audio_normalization_timeout: int = Field(default=180)
    audio_transcriber_timeout: int = Field(default=600)

    # Job timeouts (quanto tempo esperar o job completar via polling)
    video_downloader_job_timeout: int = Field(default=1800)
    audio_normalization_job_timeout: int = Field(default=3600)
    audio_transcriber_job_timeout: int = Field(default=2400)

    # Polling intervals
    poll_interval_initial: float = Field(default=2.0)
    poll_interval_max: float = Field(default=30.0)
    max_poll_attempts: int = Field(default=300)

    # Retry para requisições HTTP
    microservice_max_retries: int = Field(default=3)
    microservice_retry_delay: float = Field(default=2.0)

    # Circuit Breaker
    circuit_breaker_max_failures: int = Field(default=10)
    circuit_breaker_recovery_timeout: int = Field(default=20)
    circuit_breaker_half_open_max_requests: int = Field(default=5)

    # Timeouts para detectar jobs órfãos
    job_orphan_timeout_minutes: int = Field(default=15)
    job_heartbeat_interval_sec: int = Field(default=30)

    # Parâmetros padrão dos microserviços
    default_language: str = Field(default="auto")
    default_remove_noise: bool = Field(default=True)
    default_convert_mono: bool = Field(default=True)
    default_highpass_filter: bool = Field(default=False)
    default_sample_rate_16k: bool = Field(default=True)

    # SSL Configuration
    ssl_verify: bool = Field(default=True)
    ssl_cert_path: Optional[str] = Field(default=None)

    @field_validator("video_downloader_url", "audio_normalization_url", "audio_transcriber_url")
    @classmethod
    def validate_service_url(cls, v: Optional[str]) -> Optional[str]:
        """Valida se URL começa com http:// ou https://."""
        if v is None:
            return v
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"URL must start with http:// or https://: {v}")
        return v.rstrip("/")
    
    @model_validator(mode='after')
    def validate_required_urls(self):
        """Valida que URLs obrigatórias foram fornecidas."""
        if self.video_downloader_url is None:
            raise ValueError("video_downloader_url is required")
        if self.audio_normalization_url is None:
            raise ValueError("audio_normalization_url is required")
        if self.audio_transcriber_url is None:
            raise ValueError("audio_transcriber_url is required")
        return self

    def __getitem__(self, key: str):
        """Backward compatibility: allow dict-style access settings["key"]."""
        return getattr(self, key)

    def get(self, key: str, default=None):
        """Backward compatibility: allow settings.get("key", default)."""
        return getattr(self, key, default)

    class Config:
        """Configuração do Pydantic Settings."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> OrchestratorSettings:
    """
    Retorna instância singleton das configurações.

    Returns:
        OrchestratorSettings: Configurações carregadas do ambiente
    """
    return OrchestratorSettings()


def get_microservice_config(service_name: str) -> dict:
    """
    Retorna configuração específica de um microserviço.

    Args:
        service_name: Nome do serviço (video-downloader, audio-normalization, audio-transcriber)

    Returns:
        dict: Configuração do serviço com URL, timeouts e endpoints
    """
    settings = get_settings()

    configs = {
        "video-downloader": {
            "url": settings.video_downloader_url,
            "timeout": settings.video_downloader_timeout,
            "max_retries": settings.microservice_max_retries,
            "retry_delay": settings.microservice_retry_delay,
            "endpoints": {
                "submit": "/jobs",
                "status": "/jobs/{job_id}",
                "download": "/jobs/{job_id}/download",
                "health": "/health",
            },
        },
        "audio-normalization": {
            "url": settings.audio_normalization_url,
            "timeout": settings.audio_normalization_timeout,
            "max_retries": settings.microservice_max_retries,
            "retry_delay": settings.microservice_retry_delay,
            "endpoints": {
                "submit": "/jobs",
                "status": "/jobs/{job_id}",
                "download": "/jobs/{job_id}/download",
                "health": "/health",
            },
            "default_params": {
                "remove_noise": settings.default_remove_noise,
                "convert_to_mono": settings.default_convert_mono,
                "set_sample_rate_16k": settings.default_sample_rate_16k,
                "apply_highpass_filter": settings.default_highpass_filter,
                "isolate_vocals": False,
            },
        },
        "audio-transcriber": {
            "url": settings.audio_transcriber_url,
            "timeout": settings.audio_transcriber_timeout,
            "max_retries": settings.microservice_max_retries,
            "retry_delay": settings.microservice_retry_delay,
            "endpoints": {
                "submit": "/jobs",
                "status": "/jobs/{job_id}",
                "download": "/jobs/{job_id}/download",
                "text": "/jobs/{job_id}/text",
                "transcription": "/jobs/{job_id}/transcription",
                "health": "/health",
            },
            "default_params": {
                "language_in": settings.default_language,
            },
        },
    }
    return configs.get(service_name, {})
