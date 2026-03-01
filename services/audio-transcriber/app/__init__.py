"""
Audio Transcription Service Package
"""

from .main import app
from .workers.celery_config import celery_app

__all__ = ['app', 'celery_app']
