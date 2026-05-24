"""
Dependency Injection for Audio Transcriber service.

Factory functions that create and cache service dependencies.
"""
from functools import lru_cache
from typing import TYPE_CHECKING

from common.di import Dep
from app.core.config import get_settings
from app.infrastructure.redis_store import RedisJobStore

if TYPE_CHECKING:
    from app.services.processor import TranscriptionProcessor


@lru_cache(maxsize=1)
def _get_settings():
    return get_settings()


def get_settings_dep():
    return _get_settings()


@lru_cache(maxsize=1)
def get_job_store() -> RedisJobStore:
    import os
    settings = _get_settings()
    redis_url = os.getenv('REDIS_URL', settings.get('redis_url', 'redis://localhost:6379/0'))
    return RedisJobStore(redis_url=redis_url)


@lru_cache(maxsize=1)
def get_processor() -> "TranscriptionProcessor":
    from app.services.processor import TranscriptionProcessor

    processor = TranscriptionProcessor()
    processor.job_store = get_job_store()
    return processor


# Overridable dependencies for testing
job_store = Dep(get_job_store)
processor = Dep(get_processor)
