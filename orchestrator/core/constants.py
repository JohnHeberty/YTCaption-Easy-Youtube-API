"""Constantes do orchestrator.

Todas as configuracoes centralizadas para evitar
magic numbers espalhados pelo codigo.
"""
from datetime import timedelta


# Timeouts (segundos)
class Timeouts:
    """Timeouts para operacoes."""
    DEFAULT_JOB_TIMEOUT = 1800  # 30 minutos
    DEFAULT_POLL_INTERVAL = 5
    MAX_POLL_ATTEMPTS = 300
    REDIS_TIMEOUT = 10
    HTTP_REQUEST_TIMEOUT = 30


# Retry
class RetryConfig:
    """Configuracoes de retry."""
    MAX_ATTEMPTS = 3
    INITIAL_DELAY = 2
    MAX_DELAY = 60
    BACKOFF_MULTIPLIER = 2


# Circuit Breaker
class CircuitBreakerConfig:
    """Configuracoes do circuit breaker."""
    FAILURE_THRESHOLD = 5
    RECOVERY_TIMEOUT = 60
    HALF_OPEN_MAX_REQUESTS = 3


# Job Configuration
class JobConfig:
    """Configuracoes de jobs."""
    DEFAULT_CACHE_TTL_HOURS = 24
    DEFAULT_TIMEOUT_MINUTES = 30
    DEFAULT_POLL_INTERVAL_INITIAL = 2.0
    DEFAULT_POLL_INTERVAL_MAX = 10.0
    MAX_RETRY_ATTEMPTS = 3


# Logging
class LoggingConfig:
    """Configuracoes de logging."""
    DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DETAILED_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    DEFAULT_LEVEL = "INFO"
    MAX_BYTES = 50 * 1024 * 1024  # 50MB
    BACKUP_COUNT = 5


# API
class APIConfig:
    """Configuracoes da API."""
    DEFAULT_HOST = "0.0.0.0"
    DEFAULT_PORT = 8080
    DEFAULT_WORKERS = 4
    DEFAULT_APP_NAME = "youtube-caption-orchestrator"
    DEFAULT_APP_VERSION = "1.0.0"


# Stages
class StageType:
    """Nomes dos stages do pipeline."""
    DOWNLOAD = "download"
    NORMALIZATION = "normalization"
    TRANSCRIPTION = "transcription"


# Microservices
class Microservices:
    """Nomes dos microservicos."""
    VIDEO_DOWNLOADER = "video-downloader"
    AUDIO_NORMALIZATION = "audio-normalization"
    AUDIO_TRANSCRIBER = "audio-transcriber"


# Validation
class ValidationConstants:
    """Constantes de validacao."""
    JOB_ID_MAX_LENGTH = 64
    JOB_ID_PATTERN = r"^[a-zA-Z0-9_-]{1,64}$"


# Health Status
class HealthStatus:
    """Status de health."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
