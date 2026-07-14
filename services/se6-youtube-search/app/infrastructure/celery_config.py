from __future__ import annotations

"""
Celery configuration for youtube-search service.

Uses the shared create_celery_app factory for consistent config.
"""
from common.celery_utils import create_celery_app
from app.core.constants import (
    CELERY_TASK_TIME_LIMIT_SECONDS,
    CELERY_TASK_SOFT_TIME_LIMIT_SECONDS,
    CELERY_WORKER_MAX_TASKS_PER_CHILD,
)

celery_app = create_celery_app(
    "youtube_search",
    task_default_queue="youtube_search_queue",
    task_routes={
        "youtube_search_task": {"queue": "youtube_search_queue"},
        "cleanup_expired_jobs": {"queue": "youtube_search_queue"},
    },
    task_time_limit=CELERY_TASK_TIME_LIMIT_SECONDS,
    task_soft_time_limit=CELERY_TASK_SOFT_TIME_LIMIT_SECONDS,
    worker_max_tasks_per_child=CELERY_WORKER_MAX_TASKS_PER_CHILD,
    include=["app.infrastructure.celery_tasks"],
)