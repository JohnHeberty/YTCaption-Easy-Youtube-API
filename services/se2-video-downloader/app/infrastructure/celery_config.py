"""
Celery configuration for video-downloader service.

Uses the shared create_celery_app factory for consistent config.
"""
from common.celery_utils import create_celery_app

celery_app = create_celery_app(
    "video_downloader",
    task_default_queue="video_downloader_queue",
    task_routes={
        "download_video_task": {"queue": "video_downloader_queue"},
        "cleanup_expired_jobs": {"queue": "video_downloader_queue"},
    },
    task_time_limit=1800,
    task_soft_time_limit=1700,
    worker_max_tasks_per_child=50,
    timezone="America/Sao_Paulo",
)

# Importa tasks para registro no Celery
from . import celery_tasks  # noqa: E402, F401
