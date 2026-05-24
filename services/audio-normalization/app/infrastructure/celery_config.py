"""
Celery configuration for audio-normalization service.

Uses the shared create_celery_app factory for consistent config.
"""
import os
from common.celery_utils import create_celery_app

celery_app = create_celery_app(
    "audio_normalization",
    task_default_queue="audio_normalization_queue",
    task_routes={
        "normalize_audio_task": {"queue": "audio_normalization_queue"},
        "cleanup_expired_jobs": {"queue": "audio_normalization_queue"},
    },
    task_time_limit=int(os.getenv("CELERY_TASK_TIME_LIMIT", "1800")),
    task_soft_time_limit=int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "1500")),
    worker_prefetch_multiplier=int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1")),
    worker_max_tasks_per_child=int(os.getenv("CELERY_WORKER_MAX_TASKS_PER_CHILD", "50")),
    task_acks_late=os.getenv("CELERY_TASK_ACKS_LATE", "true").lower() == "true",
    include=["app.infrastructure.celery_tasks"],
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    worker_cancel_long_running_tasks_on_connection_loss=os.getenv(
        "CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS", "true"
    ).lower() == "true",
)
