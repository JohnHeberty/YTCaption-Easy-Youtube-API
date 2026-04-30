"""
Dependency Injection for Video Downloader service.

Factory functions that create and cache service dependencies.
Enables testability via override pattern and eliminates tight coupling to main.py globals.
"""
from functools import lru_cache
from typing import Optional

from app.core.config import get_settings
from app.infrastructure.redis_store import VideoDownloadJobStore
from app.services.video_downloader import YDLPVideoDownloader


@lru_cache(maxsize=1)
def _get_settings():
    return get_settings()


def get_settings_dep():
    return _get_settings()


@lru_cache(maxsize=1)
def get_job_store() -> VideoDownloadJobStore:
    settings = _get_settings()
    return VideoDownloadJobStore(redis_url=settings.get("redis_url", "redis://localhost:6379/0"))


@lru_cache(maxsize=1)
def get_downloader() -> YDLPVideoDownloader:
    import os
    settings = _get_settings()
    ssl_verify = os.getenv('SSL_VERIFY', 'true').lower() == 'true'
    downloader = YDLPVideoDownloader(cache_dir=settings.cache_dir, ssl_verify=ssl_verify)
    job_store = get_job_store()
    downloader.job_store = job_store
    return downloader


_job_store_override: Optional[VideoDownloadJobStore] = None
_downloader_override: Optional[YDLPVideoDownloader] = None


def get_job_store_override():
    if _job_store_override is not None:
        return _job_store_override
    return get_job_store()


def get_downloader_override():
    if _downloader_override is not None:
        return _downloader_override
    return get_downloader()


def set_job_store_override(store: Optional[VideoDownloadJobStore]):
    global _job_store_override
    _job_store_override = store


def set_downloader_override(dl: Optional[YDLPVideoDownloader]):
    global _downloader_override
    _downloader_override = dl


def reset_overrides():
    global _job_store_override, _downloader_override
    _job_store_override = None
    _downloader_override = None