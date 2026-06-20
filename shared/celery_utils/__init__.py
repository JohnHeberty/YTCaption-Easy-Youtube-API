"""
Shared Celery utilities for YTCaption microservices.

Provides a standardized factory for creating Celery applications
with consistent configuration across all services.
"""
from __future__ import annotations

from common.celery_utils.factory import create_celery_app

__all__ = ["create_celery_app"]
