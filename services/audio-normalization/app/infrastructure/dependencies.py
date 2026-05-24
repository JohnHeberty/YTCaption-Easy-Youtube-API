"""
Dependency Injection for Audio Normalization service.

Factory functions that create and cache service dependencies.
"""
from functools import lru_cache
from pathlib import Path

from common.di import Dep
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
    return _get_settings()['redis_url']


def get_upload_dir() -> Path:
    return Path(_get_settings().get('upload_dir', './uploads'))


@lru_cache(maxsize=1)
def get_job_store() -> AudioNormJobStore:
    return AudioNormJobStore(redis_url=get_redis_url())


@lru_cache(maxsize=1)
def get_audio_config() -> AudioConfig:
    return AudioConfig(_get_settings())


@lru_cache(maxsize=1)
def get_audio_processor() -> AudioProcessor:
    processor = AudioProcessor(get_audio_config())
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


# Overridable dependencies for testing
job_store = Dep(get_job_store)
audio_processor = Dep(get_audio_processor)
