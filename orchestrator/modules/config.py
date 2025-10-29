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
        
        # Limitações de recursos
        "max_file_size_mb": int(os.getenv("MAX_FILE_SIZE_MB", "500")),  # 500MB max por arquivo

        # Logging
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "log_dir": os.getenv("LOG_DIR", "./orchestrator/logs"),

        # Microserviços URLs - URLs corretas baseadas no log de erro
        "video_downloader_url": os.getenv("VIDEO_DOWNLOADER_URL", "http://192.168.18.132:8000"),
        "audio_normalization_url": os.getenv("AUDIO_NORMALIZATION_URL", "http://192.168.18.132:8001"),
        "audio_transcriber_url": os.getenv("AUDIO_TRANSCRIBER_URL", "http://192.168.18.132:8002"),

        # Timeouts dos microserviços (segundos) - Aumentados para maior resiliência
        "video_downloader_timeout": int(os.getenv("VIDEO_DOWNLOADER_TIMEOUT", "900")),   # 15min
        "audio_normalization_timeout": int(os.getenv("AUDIO_NORMALIZATION_TIMEOUT", "600")),  # 10min
        "audio_transcriber_timeout": int(os.getenv("AUDIO_TRANSCRIBER_TIMEOUT", "1200")),  # 20min

        # Polling intervals (segundos) - Polling adaptativo
        "poll_interval_initial": int(os.getenv("POLL_INTERVAL_INITIAL", "2")),  # Polling inicial rápido
        "poll_interval_max": int(os.getenv("POLL_INTERVAL_MAX", "30")),  # Polling máximo após várias tentativas
        "max_poll_attempts": int(os.getenv("MAX_POLL_ATTEMPTS", "600")),  # 30min max com polling adaptativo

        # Retry para requisições HTTP - Configuração unificada e mais robusta
        "microservice_max_retries": int(os.getenv("MICROSERVICE_MAX_RETRIES", "5")),  # Aumentado para 5
        "microservice_retry_delay": int(os.getenv("MICROSERVICE_RETRY_DELAY", "3")),  # 3s base para backoff
        "circuit_breaker_max_failures": int(os.getenv("CIRCUIT_BREAKER_MAX_FAILURES", "5")),
        "circuit_breaker_recovery_timeout": int(os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "300")),  # 5min

        # Parâmetros padrão dos microserviços
        "default_language": os.getenv("DEFAULT_LANGUAGE", "auto"),
        "default_remove_noise": os.getenv("DEFAULT_REMOVE_NOISE", "true").lower() == "true",
        "default_convert_mono": os.getenv("DEFAULT_CONVERT_MONO", "true").lower() == "true",
        "default_sample_rate_16k": os.getenv("DEFAULT_SAMPLE_RATE_16K", "true").lower() == "true",
    }

# orchestrator/modules/config.py  (trecho sugerido)
def get_microservice_config(service_name: str) -> Dict[str, Any]:
    settings = get_orchestrator_settings()

    configs = {
        "video-downloader": {
            "url": settings["video_downloader_url"],
            "timeout": settings["video_downloader_timeout"],
            "max_retries": settings["microservice_max_retries"],
            "retry_delay": settings["microservice_retry_delay"],
            "endpoints": {
                "submit": "/jobs",
                "status": "/jobs/{job_id}",
                "download": "/jobs/{job_id}/download",
                "health": "/health"
            }
        },
        "audio-normalization": {
            "url": settings["audio_normalization_url"],
            "timeout": settings["audio_normalization_timeout"],
            "max_retries": settings["microservice_max_retries"],
            "retry_delay": settings["microservice_retry_delay"],
            "endpoints": {
                # POST multipart/form-data (file + flags em texto)
                "submit": "/jobs",
                "status": "/jobs/{job_id}",
                "download": "/jobs/{job_id}/download",
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
            "max_retries": settings["microservice_max_retries"],
            "retry_delay": settings["microservice_retry_delay"],
            "endpoints": {
                # POST multipart/form-data (file + language_in/out)
                "submit": "/jobs",
                "status": "/jobs/{job_id}",
                "download": "/jobs/{job_id}/download",
                "text": "/jobs/{job_id}/text",
                "transcription": "/jobs/{job_id}/transcription",
                "health": "/health"
            },
            "default_params": {
                # no microservice o parâmetro é language_in
                "language_in": settings["default_language"]
            }
        }
    }
    return configs.get(service_name, {})