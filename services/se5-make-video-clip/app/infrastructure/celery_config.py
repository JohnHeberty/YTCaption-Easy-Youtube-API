"""
Celery Configuration for Make-Video Service
"""
from __future__ import annotations

from celery import Celery
import os
from dotenv import load_dotenv

from app.core.constants import (
    DEFAULT_CELERY_CONCURRENCY,
    DEFAULT_PREFETCH_MULTIPLIER,
    DEFAULT_CELERY_TIME_LIMIT,
    SOFT_LIMIT_RATIO,
    MAX_TASKS_PER_CHILD,
    RESULT_EXPIRY_SECONDS,
    DEFAULT_RETRY_DELAY,
    BROKER_VISIBILITY_TIMEOUT,
    CLEANUP_SCHEDULE_SECONDS,
    SHORTS_CLEANUP_SCHEDULE_SECONDS,
    ORPHAN_RECOVERY_SCHEDULE_SECONDS,
    TASK_EXPIRY_SECONDS,
)

# Load environment variables
load_dotenv()


def expand_env_vars(value: str) -> str:
    """Expand ${VAR} patterns in environment variable values"""
    if isinstance(value, str) and "${" in value:
        # Substituir ${DIVISOR} e outras variáveis
        for key in os.environ:
            placeholder = f"${{{key}}}"
            if placeholder in value:
                value = value.replace(placeholder, os.environ[key])
    return value


# Get Redis URL from environment (with variable expansion)
redis_url = expand_env_vars(os.getenv('REDIS_URL', 'redis://localhost:6379/5'))

# Get Celery worker settings from environment
celery_worker_concurrency = int(os.getenv('CELERY_WORKER_CONCURRENCY', str(DEFAULT_CELERY_CONCURRENCY)))
celery_worker_prefetch_multiplier = int(os.getenv('CELERY_WORKER_PREFETCH_MULTIPLIER', str(DEFAULT_PREFETCH_MULTIPLIER)))
celery_task_time_limit = int(os.getenv('CELERY_TASK_TIME_LIMIT', str(DEFAULT_CELERY_TIME_LIMIT)))

# Create Celery app
celery_app = Celery(
    'make-video',
    broker=redis_url,
    backend=redis_url,
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Producer settings (CRITICAL: Force serializer for producer)
    # Without this, producer.serializer stays None and messages don't reach Redis
    producer_serializer='json',
    event_serializer='json',
    
    # Task execution
    task_track_started=True,
    task_time_limit=celery_task_time_limit,  # Configurável via env
    task_soft_time_limit=int(celery_task_time_limit * SOFT_LIMIT_RATIO),
    
    # Worker settings (configuráveis via env)
    worker_concurrency=celery_worker_concurrency,
    worker_prefetch_multiplier=celery_worker_prefetch_multiplier,
    worker_max_tasks_per_child=MAX_TASKS_PER_CHILD,
    
    # Result backend
    result_expires=RESULT_EXPIRY_SECONDS,
    result_backend_transport_options={
        'master_name': 'mymaster',
    },
    
    # Retry policy
    task_default_retry_delay=DEFAULT_RETRY_DELAY,
    task_max_retries=3,
    
    # Broker transport options (Redis)
    broker_transport_options={
        'visibility_timeout': BROKER_VISIBILITY_TIMEOUT,
        'fanout_prefix': True,
        'fanout_patterns': True,
    },
    
    # Queue configuration
    task_create_missing_queues=True,  # Auto-create queues
    task_default_queue='make_video_queue',
    task_default_exchange='make_video_queue',
    task_default_routing_key='make_video_queue',
    
    # Queue routing
    task_routes={
        'app.infrastructure.celery_tasks.*': {
            'queue': 'make_video_queue',
            'exchange': 'make_video_queue',
            'routing_key': 'make_video_queue',
        },
    },
)

# Periodic tasks (Celery Beat)
celery_app.conf.beat_schedule = {
    'cleanup-temp-files': {
        'task': 'app.infrastructure.celery_tasks.cleanup_temp_files',
        'schedule': CLEANUP_SCHEDULE_SECONDS,
    },
    'cleanup-old-shorts': {
        'task': 'app.infrastructure.celery_tasks.cleanup_old_shorts',
        'schedule': SHORTS_CLEANUP_SCHEDULE_SECONDS,
    },
    # ✨ Sprint-01: Auto-recovery de jobs órfãos
    'recover-orphaned-jobs': {
        'task': 'app.infrastructure.celery_tasks.recover_orphaned_jobs',
        'schedule': ORPHAN_RECOVERY_SCHEDULE_SECONDS,
        'options': {
            'expires': TASK_EXPIRY_SECONDS,
        },
    },
}

# Import tasks to register them (must be after celery_app configuration)
from app.infrastructure import celery_tasks  # noqa: F401, E402

if __name__ == '__main__':
    celery_app.start()
