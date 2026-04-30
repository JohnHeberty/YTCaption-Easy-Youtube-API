"""
Service exceptions for the Audio Transcriber service.
Re-exports from domain.exceptions for backward compatibility.
"""
from ..domain.exceptions import (
    AudioProcessingError,
    AudioTranscriptionException,
    ServiceException,
    ResourceError,
    ProcessingTimeoutError,
    exception_handler,
)

__all__ = [
    "AudioProcessingError",
    "AudioTranscriptionException",
    "ServiceException",
    "ResourceError",
    "ProcessingTimeoutError",
    "exception_handler",
]