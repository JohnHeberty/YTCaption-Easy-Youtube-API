"""
Services module for Audio Normalization Service.

This module contains business logic services following SOLID principles.
"""

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
def _import_audio_processor():
    return AudioProcessor, AudioConfig

def _import_job_service():
    return JobCreationService, JobSubmissionService, JobRetrievalService, JobValidationResult

def _import_cleanup_service():
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
def get_audio_processor():
    AudioProcessor, AudioConfig = _import_audio_processor()
    return AudioProcessor, AudioConfig

def get_audio_config():
    _, AudioConfig = _import_audio_processor()
    return AudioConfig

def get_job_creation_service():
    JobCreationService, _, _, _ = _import_job_service()
    return JobCreationService

def get_job_submission_service():
    _, JobSubmissionService, _, _ = _import_job_service()
    return JobSubmissionService

def get_job_retrieval_service():
    _, _, JobRetrievalService, _ = _import_job_service()
    return JobRetrievalService

def get_job_validation_result():
    _, _, _, JobValidationResult = _import_job_service()
    return JobValidationResult

def get_cleanup_service():
    return _import_cleanup_service()
