"""Celery configuration for SE9 Image Engine.

Unlike SE8 (proxy), SE9 IS the GPU engine.
The Celery worker runs process_generate() directly.
"""

import os
import sys

from celery import Celery

# Ensure app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

celery_app = Celery(
    "image_engine",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/9"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/9"),
)

celery_app.conf.update(
    task_default_queue="image_engine_queue",
    task_routes={
        "app.infrastructure.celery_tasks.generate_image": {"queue": "image_engine_queue"},
        "app.infrastructure.celery_tasks.stop_generation": {"queue": "image_engine_queue"},
        "app.infrastructure.celery_tasks.cleanup_expired_jobs": {"queue": "image_engine_queue"},
    },
    task_time_limit=1200,
    task_soft_time_limit=1140,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=1,
    worker_max_tasks_per_child=1,
    timezone="America/Sao_Paulo",
    enable_utc=False,
    result_expires=3600,
)

celery_app.autodiscover_tasks(["app.infrastructure"])
