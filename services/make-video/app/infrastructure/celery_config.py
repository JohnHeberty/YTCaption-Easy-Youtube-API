"""
Celery Configuration for Make-Video Service
"""

from celery import Celery
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Redis URL from environment
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Get Celery worker settings from environment
celery_worker_concurrency = int(os.getenv('CELERY_WORKER_CONCURRENCY', '4'))
celery_worker_prefetch_multiplier = int(os.getenv('CELERY_WORKER_PREFETCH_MULTIPLIER', '1'))
celery_task_time_limit = int(os.getenv('CELERY_TASK_TIME_LIMIT', '3600'))

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
    task_soft_time_limit=int(celery_task_time_limit * 0.92),  # 92% do hard limit
    
    # Worker settings (configuráveis via env)
    worker_concurrency=celery_worker_concurrency,
    worker_prefetch_multiplier=celery_worker_prefetch_multiplier,
    worker_max_tasks_per_child=10,  # Restart worker after 10 tasks (prevent memory leaks)
    
    # Result backend
    result_expires=86400,  # Results expire after 24 hours
    result_backend_transport_options={
        'master_name': 'mymaster',
    },
    
    # Retry policy
    task_default_retry_delay=60,  # Retry after 60 seconds
    task_max_retries=3,
    
    # Broker transport options (Redis)
    broker_transport_options={
        'visibility_timeout': 3600,  # 1 hour
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
        'schedule': 3600.0,  # Every hour
    },
    'cleanup-old-shorts': {
        'task': 'app.infrastructure.celery_tasks.cleanup_old_shorts',
        'schedule': 86400.0,  # Every day
    },
    # ✨ Sprint-01: Auto-recovery de jobs órfãos
    'recover-orphaned-jobs': {
        'task': 'app.infrastructure.celery_tasks.recover_orphaned_jobs',
        'schedule': 120.0,  # A cada 2 minutos
        'options': {
            'expires': 60,  # Expirar se não executar em 1 min
        },
    },
}

# Import tasks to register them (must be after celery_app configuration)
from app.infrastructure import celery_tasks  # noqa: F401, E402

if __name__ == '__main__':
    celery_app.start()
