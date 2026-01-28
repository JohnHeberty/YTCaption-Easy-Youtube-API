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

# Create Celery app
celery_app = Celery(
    'make-video',
    broker=redis_url,
    backend=redis_url,
    include=['app.celery_tasks']  # Import tasks module
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task execution
    task_track_started=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3300,  # 55 minutes soft limit
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_max_tasks_per_child=10,  # Restart worker after 10 tasks (prevent memory leaks)
    
    # Result backend
    result_expires=86400,  # Results expire after 24 hours
    result_backend_transport_options={
        'master_name': 'mymaster',
    },
    
    # Retry policy
    task_default_retry_delay=60,  # Retry after 60 seconds
    task_max_retries=3,
    
    # Queue routing
    task_routes={
        'app.celery_tasks.*': {'queue': 'make_video_queue'},
    },
)

# Periodic tasks (Celery Beat)
celery_app.conf.beat_schedule = {
    'cleanup-temp-files': {
        'task': 'app.celery_tasks.cleanup_temp_files',
        'schedule': 3600.0,  # Every hour
    },
    'cleanup-old-shorts': {
        'task': 'app.celery_tasks.cleanup_old_shorts',
        'schedule': 86400.0,  # Every day
    },
}

if __name__ == '__main__':
    celery_app.start()
