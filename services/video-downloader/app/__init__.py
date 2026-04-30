"""Video Downloader Service application package."""

# Avoid importing from main at package level
# to prevent circular import issues and Redis connection attempts during tests

# Import specific modules instead of the full app
# from .core import validators, constants, models
# from .domain import interfaces

# Import celery tasks to ensure registration
from .infrastructure import celery_tasks
