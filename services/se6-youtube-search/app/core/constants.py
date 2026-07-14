from __future__ import annotations

"""
Core constants for YouTube Search service.
"""
from app.domain.models import SearchType, JobStatus  # noqa: F401 — canonical in models.py


class SearchLimits:
    """Limites para busca no YouTube."""
    MIN_RESULTS = 1
    MAX_RESULTS = 50
    DEFAULT_RESULTS = 10


class YouTubeAPIConfig:
    """Configurações da API do YouTube."""
    BASE_URL = "https://www.googleapis.com/youtube/v3"
    TIMEOUT_SECONDS = 30
    MAX_RETRIES = 3


# Celery Task Configuration
CELERY_TASK_TIMEOUT_SECONDS = 300  # 5 minutes for search tasks
CELERY_TASK_MAX_RETRIES = 3
CELERY_TASK_RETRY_DELAY_SECONDS = 10

# Cache Configuration
DEFAULT_CACHE_TTL_HOURS = 24
CACHE_CLEANUP_INTERVAL_MINUTES = 30

# Search Limits (deprecated, use SearchLimits class)
MAX_RESULTS_MIN = SearchLimits.MIN_RESULTS
MAX_RESULTS_MAX = SearchLimits.MAX_RESULTS
MAX_RESULTS_DEFAULT = SearchLimits.DEFAULT_RESULTS

# Timeouts
DEFAULT_SEARCH_TIMEOUT_SECONDS = 60
MAX_WAIT_TIMEOUT_SECONDS = 3600  # 1 hour for long polling
POLL_INTERVAL_SECONDS = 2

# Redis
JOB_KEY_PREFIX = "youtube_search:job:"

# Rate Limiting
DEFAULT_RATE_LIMIT_REQUESTS = 100
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60

# YouTube API Limits
MAX_VIDEOS_PER_CHANNEL = 50
MAX_RETRIES_YTBPY = 3

# Disk space thresholds (percent free)
DISK_WARNING_PERCENT = 10
DISK_CRITICAL_PERCENT = 5

# Celery hard limit offset (seconds added to soft limit for hard limit)
CELERY_HARD_LIMIT_OFFSET_SECONDS = 30

# Cleanup task timeout
CLEANUP_TASK_TIMEOUT_SECONDS = 60

# Beat schedule
BEAT_SCHEDULE_INTERVAL_SECONDS = 1800.0  # 30 minutes
BEAT_TASK_EXPIRES_SECONDS = 60  # 1 minute

# Celery config limits
CELERY_TASK_TIME_LIMIT_SECONDS = 600
CELERY_TASK_SOFT_TIME_LIMIT_SECONDS = 500
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100

# Redis connection pool
REDIS_MAX_CONNECTIONS = 50

# Thumbnail dimensions are defined in services/ytbpy/utils.py to avoid circular imports
