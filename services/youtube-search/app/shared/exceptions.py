from fastapi import Request, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class YouTubeSearchException(Exception):
    """Base exception for YouTube search service"""
    pass


class ServiceException(Exception):
    """Service-level exception"""
    pass


class ResourceError(Exception):
    """Resource access error"""
    pass


class ProcessingTimeoutError(Exception):
    """Processing timeout error"""
    pass


class InvalidRequestError(Exception):
    """Invalid request parameters"""
    pass


class YouTubeAPIError(Exception):
    """YouTube API interaction error"""
    pass


async def exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"❌ Exception in {request.url.path}: {str(exc)}", exc_info=True)
    
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    if isinstance(exc, InvalidRequestError):
        status_code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, ResourceError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ProcessingTimeoutError):
        status_code = status.HTTP_408_REQUEST_TIMEOUT
    
    return JSONResponse(
        status_code=status_code,
        content={"detail": str(exc), "type": exc.__class__.__name__}
    )
