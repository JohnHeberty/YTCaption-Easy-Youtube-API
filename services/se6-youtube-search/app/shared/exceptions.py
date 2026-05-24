"""
Service-specific exceptions for YouTube Search.

All exceptions inherit from BaseServiceException so they are automatically
handled by common.exception_handlers.setup_exception_handlers().
"""
from fastapi import status
from common.exception_handlers import BaseServiceException


class YouTubeSearchException(BaseServiceException):
    """Base exception for YouTube search service."""

    def __init__(self, message: str = "YouTube search error"):
        super().__init__(message=message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, error_code="YOUTUBE_SEARCH_ERROR")


class ServiceException(BaseServiceException):
    """Service-level exception."""

    def __init__(self, message: str = "Service error"):
        super().__init__(message=message, error_code="SERVICE_ERROR")


class InvalidRequestError(BaseServiceException):
    """Invalid request parameters."""

    def __init__(self, message: str = "Invalid request"):
        super().__init__(message=message, status_code=status.HTTP_400_BAD_REQUEST, error_code="INVALID_REQUEST")


class ResourceError(BaseServiceException):
    """Resource access error."""

    def __init__(self, message: str = "Resource error"):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND, error_code="RESOURCE_ERROR")


class ProcessingTimeoutError(BaseServiceException):
    """Processing timeout error."""

    def __init__(self, message: str = "Processing timeout"):
        super().__init__(message=message, status_code=status.HTTP_408_REQUEST_TIMEOUT, error_code="PROCESSING_TIMEOUT")


class YouTubeAPIError(BaseServiceException):
    """YouTube API interaction error."""

    def __init__(self, message: str = "YouTube API error"):
        super().__init__(message=message, error_code="YOUTUBE_API_ERROR")
