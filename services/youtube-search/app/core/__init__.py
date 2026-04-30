"""
Core layer for YouTube Search service.

Provides configuration, validators, constants, and models.
"""

from .config import get_settings
from .constants import (
    SearchType,
    JobStatus,
    CELERY_TASK_TIMEOUT_SECONDS,
    CELERY_TASK_MAX_RETRIES,
    DEFAULT_CACHE_TTL_HOURS,
    MAX_RESULTS_MIN,
    MAX_RESULTS_MAX,
    DEFAULT_SEARCH_TIMEOUT_SECONDS,
    POLL_INTERVAL_SECONDS,
)
from .validators import (
    ValidationError,
    JobIdValidator,
    MaxResultsValidator,
    TimeoutValidator,
    QueryValidator,
)

__all__ = [
    "get_settings",
    "SearchType",
    "JobStatus",
    "CELERY_TASK_TIMEOUT_SECONDS",
    "CELERY_TASK_MAX_RETRIES",
    "DEFAULT_CACHE_TTL_HOURS",
    "MAX_RESULTS_MIN",
    "MAX_RESULTS_MAX",
    "DEFAULT_SEARCH_TIMEOUT_SECONDS",
    "POLL_INTERVAL_SECONDS",
    "ValidationError",
    "JobIdValidator",
    "MaxResultsValidator",
    "TimeoutValidator",
    "QueryValidator",
]
