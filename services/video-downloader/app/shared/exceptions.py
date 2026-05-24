"""
Service-specific exceptions for Video Downloader.

All exceptions inherit from BaseServiceException so they are automatically
handled by common.exception_handlers.setup_exception_handlers().
"""
from fastapi import status
from common.exception_handlers import BaseServiceException


class VideoDownloadException(BaseServiceException):
    """Base exception for video download errors."""

    def __init__(self, message: str = "Video download error", status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        super().__init__(message=message, status_code=status_code, error_code="VIDEO_DOWNLOAD_ERROR")


class ServiceException(BaseServiceException):
    """Service-level exception."""

    def __init__(self, message: str = "Service error"):
        super().__init__(message=message, error_code="SERVICE_ERROR")


class ResourceError(BaseServiceException):
    """Resource not found or unavailable."""

    def __init__(self, message: str = "Resource error"):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND, error_code="RESOURCE_ERROR")


class ProcessingTimeoutError(BaseServiceException):
    """Processing exceeded time limit."""

    def __init__(self, message: str = "Processing timeout"):
        super().__init__(message=message, status_code=status.HTTP_408_REQUEST_TIMEOUT, error_code="PROCESSING_TIMEOUT")


class AudioProcessingError(BaseServiceException):
    """Audio processing error (compatibility)."""

    def __init__(self, message: str = "Audio processing error"):
        super().__init__(message=message, error_code="AUDIO_PROCESSING_ERROR")
