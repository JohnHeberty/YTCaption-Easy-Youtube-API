from fastapi import Request, status
from fastapi.responses import JSONResponse
from common.log_utils import get_logger

logger = get_logger(__name__)

class AudioProcessingError(Exception):
    pass

class AudioTranscriptionException(Exception):
    pass

class ServiceException(Exception):
    pass

class ResourceError(Exception):
    pass

class ProcessingTimeoutError(Exception):
    pass

async def exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"❌ Exception in {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)}
    )
