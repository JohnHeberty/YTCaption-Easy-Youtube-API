from __future__ import annotations

"""
Celery configuration for youtube-search service.

Uses the shared create_celery_app factory for consistent config.
"""
from common.celery_utils import create_celery_app

celery_app = create_celery_app(
    "youtube_search",
    task_default_queue="youtube_search_queue",
    task_routes={
        "youtube_search_task": {"queue": "youtube_search_queue"},
        "cleanup_expired_jobs": {"queue": "youtube_search_queue"},
    },
    task_time_limit=600,
    task_soft_time_limit=500,
    worker_max_tasks_per_child=100,
    include=["app.infrastructure.celery_tasks"],
)
