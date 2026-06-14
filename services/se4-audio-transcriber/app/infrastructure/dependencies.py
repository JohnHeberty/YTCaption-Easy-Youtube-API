"""
Dependency Injection for Audio Transcriber service.

Factory functions that create and cache service dependencies.
Returns abstract types (IJobStore, ITranscriptionProcessor) to satisfy DIP.
Concrete implementations are resolved lazily inside the factory.
"""
from functools import lru_cache
from typing import TYPE_CHECKING

import os

from common.di import Dep
from app.core.config import get_settings
from app.domain.interfaces import IJobStore, ITranscriptionService

if TYPE_CHECKING:
    from app.services.processor import TranscriptionProcessor


@lru_cache(maxsize=1)
def _get_settings():
    return get_settings()


def get_settings_dep():
    return _get_settings()


@lru_cache(maxsize=1)
def get_job_store() -> IJobStore:
    from app.infrastructure.redis_store import RedisJobStore

    settings = _get_settings()
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    if isinstance(settings, dict):
        redis_url = os.getenv('REDIS_URL', settings.get('redis_url', redis_url))
    return RedisJobStore(redis_url=redis_url)


@lru_cache(maxsize=1)
def get_transcription_service() -> ITranscriptionService:
    from app.services.transcription_service import TranscriptionService

    return TranscriptionService(
        job_store=get_job_store(),
    )


@lru_cache(maxsize=1)
def get_processor() -> "TranscriptionProcessor":
    from app.services.processor import TranscriptionProcessor

    processor = TranscriptionProcessor()
    processor.job_store = get_job_store()
    return processor


# Overridable dependencies for testing
job_store = Dep(get_job_store)
transcription_service = Dep(get_transcription_service)
processor = Dep(get_processor)
