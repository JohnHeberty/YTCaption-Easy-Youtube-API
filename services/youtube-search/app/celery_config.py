import os
from celery import Celery


# Redis/Celery configuration via .env
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
celery_broker = os.getenv('CELERY_BROKER_URL', redis_url)
celery_backend = os.getenv('CELERY_RESULT_BACKEND', redis_url)

# Configurable timeouts
task_time_limit = int(os.getenv('CELERY_TASK_TIME_LIMIT', '600'))
task_soft_time_limit = int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', '500'))

# Result TTL (based on CACHE_TTL_HOURS)
cache_ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
result_expires = cache_ttl_hours * 3600

# Initialize Celery
celery_app = Celery(
    'youtube_search_tasks',
    broker=celery_broker,
    backend=celery_backend
)

# Configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    # Result TTL (configurable via CACHE_TTL_HOURS)
    result_expires=result_expires,
    # Task timeout (configurable via .env)
    task_time_limit=task_time_limit,
    task_soft_time_limit=task_soft_time_limit,
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    broker_connection_retry_on_startup=True,
    # 🔧 DEDICATED QUEUE for youtube-search
    task_default_queue='youtube_search_queue',
    task_routes={
        'youtube_search_task': {'queue': 'youtube_search_queue'},
        'cleanup_expired_jobs': {'queue': 'youtube_search_queue'},
    },
    # Auto-discovery of tasks
    include=['app.celery_tasks']
)
