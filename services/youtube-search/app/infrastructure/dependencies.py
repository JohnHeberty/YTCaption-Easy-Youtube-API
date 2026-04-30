"""
Dependency Injection for YouTube Search service.

Factory functions that create and cache service dependencies.
"""
from functools import lru_cache
from typing import Optional

from app.core.config import get_settings
from app.infrastructure.redis_store import YouTubeSearchJobStore as RedisJobStore


@lru_cache(maxsize=1)
def _get_settings():
    return get_settings()


def get_settings_dep():
    return _get_settings()


@lru_cache(maxsize=1)
def get_job_store() -> RedisJobStore:
    settings = _get_settings()
    return RedisJobStore(redis_url=settings.get('redis_url', 'redis://localhost:6379/0'))


_job_store_override: Optional[RedisJobStore] = None


def get_job_store_override():
    if _job_store_override is not None:
        return _job_store_override
    return get_job_store()


def set_job_store_override(store: Optional[RedisJobStore]):
    global _job_store_override
    _job_store_override = store


def reset_overrides():
    global _job_store_override
    _job_store_override = None