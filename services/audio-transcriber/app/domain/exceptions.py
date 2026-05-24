"""
Service-specific exceptions for Audio Transcriber.

All exceptions inherit from BaseServiceException so they are automatically
handled by common.exception_handlers.setup_exception_handlers().
"""
from fastapi import status
from common.exception_handlers import BaseServiceException


class AudioProcessingError(BaseServiceException):
    def __init__(self, message: str = "Audio processing error"):
        super().__init__(message=message, error_code="AUDIO_PROCESSING_ERROR")


class AudioTranscriptionException(BaseServiceException):
    def __init__(self, message: str = "Transcription error"):
        super().__init__(message=message, error_code="AUDIO_TRANSCRIPTION_ERROR")


class ServiceException(BaseServiceException):
    def __init__(self, message: str = "Service error"):
        super().__init__(message=message, error_code="SERVICE_ERROR")


class ResourceError(BaseServiceException):
    def __init__(self, message: str = "Resource error"):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND, error_code="RESOURCE_ERROR")


class ProcessingTimeoutError(BaseServiceException):
    def __init__(self, message: str = "Processing timeout"):
        super().__init__(message=message, status_code=status.HTTP_408_REQUEST_TIMEOUT, error_code="PROCESSING_TIMEOUT")
