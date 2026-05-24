"""
Dependency Injection for YouTube Search service.

Factory functions that create and cache service dependencies.
"""
from functools import lru_cache

from common.di import Dep
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


job_store = Dep(get_job_store)
