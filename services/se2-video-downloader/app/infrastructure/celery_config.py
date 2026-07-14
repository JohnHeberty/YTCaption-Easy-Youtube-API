from __future__ import annotations

"""
Celery configuration for video-downloader service.

Uses the shared create_celery_app factory for consistent config.
"""
from common.celery_utils import create_celery_app
from ..core.constants import (
    DEFAULT_JOB_TIMEOUT_SECONDS,
    CELERY_SOFT_TIME_LIMIT_SECONDS,
    CELERY_WORKER_MAX_TASKS_PER_CHILD,
)

celery_app = create_celery_app(
    "video_downloader",
    task_default_queue="video_downloader_queue",
    task_routes={
        "download_video_task": {"queue": "video_downloader_queue"},
        "cleanup_expired_jobs": {"queue": "video_downloader_queue"},
    },
    task_time_limit=DEFAULT_JOB_TIMEOUT_SECONDS,
    task_soft_time_limit=CELERY_SOFT_TIME_LIMIT_SECONDS,
    worker_max_tasks_per_child=CELERY_WORKER_MAX_TASKS_PER_CHILD,
    timezone="America/Sao_Paulo",
)

# Importa tasks para registro no Celery
from . import celery_tasks  # noqa: E402, F401
