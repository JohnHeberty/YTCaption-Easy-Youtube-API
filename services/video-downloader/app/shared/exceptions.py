from fastapi import Request, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class VideoDownloadException(Exception):
    """Base exception for video download errors."""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ServiceException(Exception):
    """Service-level exception."""
    pass


class AudioProcessingError(Exception):
    """Audio processing error (compatibility)."""
    pass


class ResourceError(Exception):
    """Resource not found or unavailable."""
    pass


class ProcessingTimeoutError(Exception):
    """Processing exceeded time limit."""
    pass


async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Unified async exception handler — returns consistent JSON for all errors."""
    logger.error(
        "Exception in %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )

    if isinstance(exc, VideoDownloadException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "type": exc.__class__.__name__},
        )
    if isinstance(exc, ResourceError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc), "type": "ResourceError"},
        )
    if isinstance(exc, ProcessingTimeoutError):
        return JSONResponse(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            content={"detail": str(exc), "type": "ProcessingTimeoutError"},
        )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc), "type": exc.__class__.__name__},
    )