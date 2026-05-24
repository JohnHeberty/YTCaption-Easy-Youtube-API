"""
Dependency Injection for Make Video service.

Factory functions that create and cache service dependencies.
"""
from functools import lru_cache
from typing import Optional

from app.core.config import get_settings
from app.infrastructure.redis_store import MakeVideoJobStore as RedisJobStore
from app.infrastructure.lock_manager import DistributedLockManager
from app.services.job_manager import JobManager
from app.services.cache_manager import CacheManager
from app.api.api_client import MicroservicesClient


@lru_cache(maxsize=1)
def _get_settings():
    return get_settings()


def get_settings_dep():
    return _get_settings()


@lru_cache(maxsize=1)
def get_redis_store() -> RedisJobStore:
    settings = _get_settings()
    return RedisJobStore(redis_url=settings['redis_url'])


@lru_cache(maxsize=1)
def get_job_manager() -> JobManager:
    redis_store = get_redis_store()
    return JobManager(redis_store=redis_store)


@lru_cache(maxsize=1)
def get_cache_manager() -> CacheManager:
    settings = _get_settings()
    return CacheManager(cache_dir=settings['shorts_cache_dir'])


@lru_cache(maxsize=1)
def get_lock_manager() -> DistributedLockManager:
    settings = _get_settings()
    return DistributedLockManager(redis_url=settings['redis_url'])


@lru_cache(maxsize=1)
def get_api_client() -> MicroservicesClient:
    settings = _get_settings()
    return MicroservicesClient(
        youtube_search_url=settings['youtube_search_url'],
        video_downloader_url=settings['video_downloader_url'],
        audio_transcriber_url=settings['audio_transcriber_url']
    )


_redis_store_override = None
_job_manager_override = None
_cache_manager_override = None
_lock_manager_override = None
_api_client_override = None


def get_redis_store_override():
    if _redis_store_override is not None:
        return _redis_store_override
    return get_redis_store()


def get_job_manager_override():
    if _job_manager_override is not None:
        return _job_manager_override
    return get_job_manager()


def get_cache_manager_override():
    if _cache_manager_override is not None:
        return _cache_manager_override
    return get_cache_manager()


def get_lock_manager_override():
    if _lock_manager_override is not None:
        return _lock_manager_override
    return get_lock_manager()


def get_api_client_override():
    if _api_client_override is not None:
        return _api_client_override
    return get_api_client()


def reset_overrides():
    global _redis_store_override, _job_manager_override, _cache_manager_override, _lock_manager_override, _api_client_override
    _redis_store_override = None
    _job_manager_override = None
    _cache_manager_override = None
    _lock_manager_override = None
    _api_client_override = None