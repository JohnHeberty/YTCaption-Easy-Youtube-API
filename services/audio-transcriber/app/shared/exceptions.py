"""
Service exceptions for the Audio Transcriber service.
Re-exports from domain.exceptions for backward compatibility.

All exceptions inherit from BaseServiceException so they are automatically
handled by common.exception_handlers.setup_exception_handlers().
"""
from ..domain.exceptions import (
    AudioProcessingError,
    AudioTranscriptionException,
    ServiceException,
    ResourceError,
    ProcessingTimeoutError,
)

__all__ = [
    "AudioProcessingError",
    "AudioTranscriptionException",
    "ServiceException",
    "ResourceError",
    "ProcessingTimeoutError",
]