#config.py
"""
Configurações da API Orquestradora
Carrega variáveis de ambiente e configurações dos microserviços
"""
import os
from typing import Dict, Any
from pathlib import Path


def get_orchestrator_settings() -> Dict[str, Any]:
    """Retorna configurações do orquestrador"""
    return {
        # Aplicação
        "app_name": os.getenv("APP_NAME", "ytcaption-orchestrator"),
        "app_version": os.getenv("APP_VERSION", "1.0.0"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "debug": os.getenv("DEBUG", "false").lower() == "true",

        # Servidor
        "app_host": os.getenv("HOST", "0.0.0.0"),
        "app_port": int(os.getenv("PORT", "8080")),
        "workers": int(os.getenv("WORKERS", "1")),

        # Redis
        "redis_url": os.getenv("REDIS_URL", "redis://192.168.18.110:6379/0"),

        # Cache e TTL
        "cache_ttl_hours": int(os.getenv("CACHE_TTL_HOURS", "24")),
        "job_timeout_minutes": int(os.getenv("JOB_TIMEOUT_MINUTES", "60")),

        # HTTP/Resiliência
        "http_max_retries": int(os.getenv("HTTP_MAX_RETRIES", "3")),
        "retry_backoff_base_seconds": float(os.getenv("RETRY_BACKOFF_BASE_SECONDS", "1.5")),

        # Logging
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "log_dir": os.getenv("LOG_DIR", "./orchestrator/logs"),

        # Microserviços URLs
        "video_downloader_url": os.getenv("VIDEO_DOWNLOADER_URL", "http://192.168.18.203:8000"),
        "audio_normalization_url": os.getenv("AUDIO_NORMALIZATION_URL", "http://192.168.18.203:8001"),
        "audio_transcriber_url": os.getenv("AUDIO_TRANSCRIBER_URL", "http://192.168.18.203:8002"),

        # Timeouts dos microserviços (segundos)
        "video_downloader_timeout": int(os.getenv("VIDEO_DOWNLOADER_TIMEOUT", "300")),   # 5min
        "audio_normalization_timeout": int(os.getenv("AUDIO_NORMALIZATION_TIMEOUT", "180")),  # 3min
        "audio_transcriber_timeout": int(os.getenv("AUDIO_TRANSCRIBER_TIMEOUT", "600")),  # 10min

        # Polling intervals (segundos)
        "poll_interval": int(os.getenv("POLL_INTERVAL", "2")),
        "max_poll_attempts": int(os.getenv("MAX_POLL_ATTEMPTS", "300")),  # 10min com poll de 2s

        # Parâmetros padrão dos microserviços
        "default_language": os.getenv("DEFAULT_LANGUAGE", "auto"),
        "default_remove_noise": os.getenv("DEFAULT_REMOVE_NOISE", "true").lower() == "true",
        "default_convert_mono": os.getenv("DEFAULT_CONVERT_MONO", "true").lower() == "true",
        "default_sample_rate_16k": os.getenv("DEFAULT_SAMPLE_RATE_16K", "true").lower() == "true",
    }


def get_microservice_config(service_name: str) -> Dict[str, Any]:
    """Retorna configuração específica de um microserviço"""
    settings = get_orchestrator_settings()

    configs = {
        "video-downloader": {
            "url": settings["video_downloader_url"],
            "timeout": settings["video_downloader_timeout"],
            "endpoints": {
                # Alias 'submit' pra evitar bugs no cliente
                "submit": "/download",
                "download": "/download",
                "status": "/jobs/{job_id}",
                "health": "/health"
            }
        },
        "audio-normalization": {
            "url": settings["audio_normalization_url"],
            "timeout": settings["audio_normalization_timeout"],
            "endpoints": {
                "submit": "/jobs",
                "process": "/jobs",
                "status": "/jobs/{job_id}",
                "health": "/health"
            },
            "default_params": {
                "remove_noise": settings["default_remove_noise"],
                "convert_to_mono": settings["default_convert_mono"],
                "set_sample_rate_16k": settings["default_sample_rate_16k"],
                "apply_highpass_filter": False,
                "isolate_vocals": False
            }
        },
        "audio-transcriber": {
            "url": settings["audio_transcriber_url"],
            "timeout": settings["audio_transcriber_timeout"],
            "endpoints": {
                "submit": "/jobs",
                "transcribe": "/jobs",
                "status": "/jobs/{job_id}",
                "health": "/health",
                "languages": "/languages"
            },
            "default_params": {
                "language": settings["default_language"]
            }
        }
    }

    return configs.get(service_name, {})
