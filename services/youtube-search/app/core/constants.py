"""
Core constants for YouTube Search service.
"""

from enum import Enum
from datetime import timedelta


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


class SearchType(str, Enum):
    """Types of YouTube searches supported."""

    VIDEO = "video"
    CHANNEL = "channel"
    PLAYLIST = "playlist"
    VIDEO_INFO = "video_info"
    CHANNEL_INFO = "channel_info"
    PLAYLIST_INFO = "playlist_info"
    RELATED_VIDEOS = "related_videos"
    SHORTS = "shorts"


class JobStatus(str, Enum):
    """Job status values."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


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
