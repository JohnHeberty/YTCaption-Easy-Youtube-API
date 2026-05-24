"""
Dependency Injection for Video Downloader service.

Factory functions that create and cache service dependencies.
"""
from functools import lru_cache

from common.di import Dep
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
    downloader.job_store = get_job_store()
    return downloader


job_store = Dep(get_job_store)
downloader = Dep(get_downloader)
