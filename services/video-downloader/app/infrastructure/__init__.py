"""Infrastructure module for video-downloader service."""

# Import celery tasks to ensure registration
from . import celery_tasks
