"""
Dependency Injection for Audio Normalization service.

Factory functions that create and cache service dependencies.
Enables testability via override pattern.
"""
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.infrastructure.redis_store import AudioNormJobStore
from app.services.audio_processor import AudioProcessor, AudioConfig
from app.services.job_service import (
    JobCreationService,
    JobSubmissionService,
    JobRetrievalService,
)


@lru_cache(maxsize=1)
def _get_settings():
    return get_settings()


def get_settings_dep():
    return _get_settings()


def get_redis_url() -> str:
    settings = _get_settings()
    return settings['redis_url']


def get_upload_dir() -> Path:
    settings = _get_settings()
    return Path(settings.get('upload_dir', './uploads'))


@lru_cache(maxsize=1)
def get_job_store() -> AudioNormJobStore:
    return AudioNormJobStore(redis_url=get_redis_url())


@lru_cache(maxsize=1)
def get_audio_config() -> AudioConfig:
    settings = _get_settings()
    return AudioConfig(settings)


@lru_cache(maxsize=1)
def get_audio_processor() -> AudioProcessor:
    config = get_audio_config()
    processor = AudioProcessor(config)
    processor.set_job_store(get_job_store())
    return processor


def get_job_creation_service() -> JobCreationService:
    return JobCreationService(
        job_store=get_job_store(),
        upload_dir=get_upload_dir(),
        max_file_size_mb=_get_settings()['max_file_size_mb']
    )


def get_job_submission_service() -> JobSubmissionService:
    return JobSubmissionService(job_store=get_job_store())


def get_job_retrieval_service() -> JobRetrievalService:
    return JobRetrievalService(job_store=get_job_store())


# Override pattern for tests
_job_store_override: Optional[AudioNormJobStore] = None
_audio_processor_override: Optional[AudioProcessor] = None


def get_job_store_override():
    if _job_store_override is not None:
        return _job_store_override
    return get_job_store()


def get_audio_processor_override():
    if _audio_processor_override is not None:
        return _audio_processor_override
    return get_audio_processor()


def set_job_store_override(store: Optional[AudioNormJobStore]):
    global _job_store_override
    _job_store_override = store


def set_audio_processor_override(proc: Optional[AudioProcessor]):
    global _audio_processor_override
    _audio_processor_override = proc


def reset_overrides():
    global _job_store_override, _audio_processor_override
    _job_store_override = None
    _audio_processor_override = None