"""
Dependency Injection for Audio Transcriber service.

Factory functions that create and cache service dependencies.
Enables testability via override pattern and eliminates tight coupling to main.py globals.
"""
from functools import lru_cache
from typing import Optional, TYPE_CHECKING

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
    job_store = get_job_store()
    processor.job_store = job_store
    return processor


_job_store_override: Optional[RedisJobStore] = None
_processor_override: Optional["TranscriptionProcessor"] = None


def get_job_store_override():
    if _job_store_override is not None:
        return _job_store_override
    return get_job_store()


def get_processor_override():
    if _processor_override is not None:
        return _processor_override
    return get_processor()


def set_job_store_override(store: Optional[RedisJobStore]):
    global _job_store_override
    _job_store_override = store


def set_processor_override(proc: Optional["TranscriptionProcessor"]):
    global _processor_override
    _processor_override = proc


def reset_overrides():
    global _job_store_override, _processor_override
    _job_store_override = None
    _processor_override = None