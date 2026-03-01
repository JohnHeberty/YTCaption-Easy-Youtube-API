"""
Celery Configuration Proxy

This module provides backward compatibility for importing celery_app from app.celery_config
The actual configuration is in app/workers/celery_config.py
"""

from .workers.celery_config import celery_app

__all__ = ['celery_app']
