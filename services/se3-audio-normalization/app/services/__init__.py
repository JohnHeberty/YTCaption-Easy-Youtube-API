"""
Services module for Audio Normalization Service.

This module contains business logic services following SOLID principles.
"""
from __future__ import annotations

# Direct imports for Celery tasks
from .audio_processor import AudioProcessor, AudioConfig
from .file_validator import FileValidator
from .audio_extractor import AudioExtractor
from .audio_normalizer import AudioNormalizer
from .job_manager import JobManager
from .job_service import (
    JobCreationService,
    JobSubmissionService,
    JobRetrievalService,
    JobValidationResult,
)
from .cleanup_service import CleanupService

# Lazy imports to avoid dependency issues
def _import_audio_processor() -> tuple[type[AudioProcessor], type[AudioConfig]]:
    return AudioProcessor, AudioConfig

def _import_job_service() -> tuple[type[JobCreationService], type[JobSubmissionService], type[JobRetrievalService], type[JobValidationResult]]:
    return JobCreationService, JobSubmissionService, JobRetrievalService, JobValidationResult

def _import_cleanup_service() -> type[CleanupService]:
    return CleanupService

__all__ = [
    # Audio Processing
    "AudioProcessor",
    "AudioConfig",
    "get_audio_processor",
    "get_audio_config",
    # File Handling
    "FileValidator",
    # Audio Pipeline
    "AudioExtractor",
    "AudioNormalizer",
    # Job Management
    "JobManager",
    "JobCreationService",
    "JobSubmissionService",
    "JobRetrievalService",
    "JobValidationResult",
    "get_job_creation_service",
    "get_job_submission_service",
    "get_job_retrieval_service",
    "get_job_validation_result",
    # Cleanup
    "CleanupService",
    "get_cleanup_service",
]

# Helper functions for lazy loading
def get_audio_processor() -> tuple[type[AudioProcessor], type[AudioConfig]]:
    AudioProcessor, AudioConfig = _import_audio_processor()
    return AudioProcessor, AudioConfig

def get_audio_config() -> type[AudioConfig]:
    _, AudioConfig = _import_audio_processor()
    return AudioConfig

def get_job_creation_service() -> type[JobCreationService]:
    JobCreationService, _, _, _ = _import_job_service()
    return JobCreationService

def get_job_submission_service() -> type[JobSubmissionService]:
    _, JobSubmissionService, _, _ = _import_job_service()
    return JobSubmissionService

def get_job_retrieval_service() -> type[JobRetrievalService]:
    _, _, JobRetrievalService, _ = _import_job_service()
    return JobRetrievalService

def get_job_validation_result() -> type[JobValidationResult]:
    _, _, _, JobValidationResult = _import_job_service()
    return JobValidationResult

def get_cleanup_service() -> type[CleanupService]:
    return _import_cleanup_service()
