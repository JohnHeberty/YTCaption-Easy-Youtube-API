"""
Core module for Audio Normalization Service.

Contains fundamental components: models, validators, exceptions, constants.
"""

from .models import Job, JobStatus, AudioProcessingRequest
from .exceptions import (
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
from .constants import (
    AudioConstants,
    JobConstants,
    FileConstants,
    ValidationConstants,
)
from .validators import (
    JobIdValidator,
    BooleanValidator,
    FileValidator,
    ProcessingParamsValidator,
    PathValidator,
    ValidationError as ValidatorError,
    FileTooLargeError,
    InvalidFileFormatError,
)

__all__ = [
    # Models
    "Job",
    "JobStatus",
    "AudioProcessingRequest",
    # Exceptions
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
    # Constants
    "AudioConstants",
    "JobConstants",
    "FileConstants",
    "ValidationConstants",
    # Validators
    "JobIdValidator",
    "BooleanValidator",
    "FileValidator",
    "ProcessingParamsValidator",
    "PathValidator",
    "ValidatorError",
    "FileTooLargeError",
    "InvalidFileFormatError",
]
