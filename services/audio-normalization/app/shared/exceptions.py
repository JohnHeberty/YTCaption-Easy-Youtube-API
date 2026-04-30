"""
Domain exceptions for the Audio Normalization service.

Backward-compatible: all exceptions are now defined in core.exceptions.
This module re-exports them for any code that imports from shared.exceptions.
"""
from ..core.exceptions import (
    AudioNormalizationError,
    AudioNormalizationException,
    InvalidAudioFormat,
    FileTooLarge,
    ProcessingError,
    RedisError,
    JobNotFoundError,
    JobExpiredError,
    StorageError,
    ValidationError,
    CeleryTaskError,
    FileValidationError,
    ResourceNotFoundError,
    ProcessingTimeoutError,
    ResourceError,
)

__all__ = [
    "AudioNormalizationError",
    "AudioNormalizationException",
    "InvalidAudioFormat",
    "FileTooLarge",
    "ProcessingError",
    "RedisError",
    "JobNotFoundError",
    "JobExpiredError",
    "StorageError",
    "ValidationError",
    "CeleryTaskError",
    "FileValidationError",
    "ResourceNotFoundError",
    "ProcessingTimeoutError",
    "ResourceError",
]