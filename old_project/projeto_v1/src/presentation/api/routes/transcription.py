"""
Rotas de transcrição.
Endpoints para transcrição de vídeos do YouTube.

v2.1: Rate limiting para prevenir abuso.
v2.2: Circuit breaker + Prometheus metrics.
"""
from time import time
from fastapi import APIRouter, Depends, HTTPException, status, Request
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.application.use_cases import TranscribeYouTubeVideoUseCase
from src.application.dtos import (
    TranscribeRequestDTO,
    TranscribeResponseDTO,
    ErrorResponseDTO
)
from src.domain.exceptions import (
    VideoDownloadError,
    TranscriptionError,
    ValidationError,
    AudioTooLongError,
    AudioCorruptedError,
    OperationTimeoutError,
    NetworkError
)
from src.infrastructure.utils import CircuitBreakerOpenError
from src.infrastructure.monitoring import MetricsCollector
from src.presentation.api.dependencies import get_transcribe_use_case, raise_error


router = APIRouter(prefix="/api/v1/transcribe", tags=["Transcription"])

# Rate limiter instance
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "",
    response_model=TranscribeResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Transcribe YouTube video",
    description="""
    Downloads a YouTube video and transcribes its audio using Whisper AI or YouTube's native transcripts.
    
    **⚡ Rate Limit:** 5 requests per minute per IP address
    
    **Processing Time:**
    - With YouTube transcripts: ~2-5 seconds
    - With Whisper: ~30-120 seconds (depends on video duration and model)
    
    **Automatic Timeout:** Based on video duration to prevent hanging requests.
    
    If rate limit is exceeded, returns HTTP 429 with retry information.
    """,
    responses={
        200: {
            "description": "Transcription successful",
            "model": TranscribeResponseDTO,
            "headers": {
                "X-Request-ID": {
                    "description": "Unique request identifier for tracking",
                    "schema": {"type": "string", "format": "uuid"}
                },
                "X-Process-Time": {
                    "description": "Processing time in seconds",
                    "schema": {"type": "string"}
                }
            }
        },
        400: {
            "description": "Bad Request (validation error, audio too long, corrupted)",
            "model": ErrorResponseDTO,
            "content": {
                "application/json": {
                    "examples": {
                        "audio_too_long": {
                            "summary": "Audio exceeds maximum duration",
                            "value": {
                                "error": "AudioTooLongError",
                                "message": "Audio duration (7250s) exceeds maximum allowed (7200s)",
                                "request_id": "abc-123-def",
                                "details": {"duration": 7250, "max_duration": 7200}
                            }
                        },
                        "validation": {
                            "summary": "Invalid YouTube URL",
                            "value": {
                                "error": "ValidationError",
                                "message": "Must be a valid YouTube URL",
                                "request_id": "abc-123-def",
                                "details": {}
                            }
                        }
                    }
                }
            }
        },
        404: {
            "description": "Video not found or download error",
            "model": ErrorResponseDTO
        },
        429: {
            "description": "Rate limit exceeded - 5 requests per minute per IP",
            "model": ErrorResponseDTO,
            "content": {
                "application/json": {
                    "example": {
                        "error": "RateLimitExceeded",
                        "message": "Rate limit exceeded: 5 per 1 minute",
                        "request_id": "abc-123-def",
                        "details": {"limit": "5/minute", "retry_after_seconds": 60}
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponseDTO
        },
        503: {
            "description": "Service unavailable (Circuit Breaker open)",
            "model": ErrorResponseDTO
        },
        504: {
            "description": "Gateway timeout - Operation took too long",
            "model": ErrorResponseDTO
        }
    }
)
@limiter.limit("5/minute")
async def transcribe_video(
    request: Request,
    request_dto: TranscribeRequestDTO,
    use_case: TranscribeYouTubeVideoUseCase = Depends(get_transcribe_use_case)
) -> TranscribeResponseDTO:
    """
    Transcreve um vídeo do YouTube.
    
    - **youtube_url**: URL completa do vídeo do YouTube
    - **language**: Código do idioma (opcional, 'auto' para detecção automática)
    
    Retorna a transcrição completa com segmentos timestampados.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        logger.info(
            "📝 Transcription request received",
            extra={
                "request_id": request_id,
                "youtube_url": request_dto.youtube_url,
                "language": request_dto.language,
                "client_ip": request.client.host if request.client else "unknown"
            }
        )
        
        response = await use_case.execute(request_dto)
        
        logger.info(
            "✅ Transcription successful",
            extra={
                "request_id": request_id,
                "transcription_id": response.transcription_id,
                "total_segments": response.total_segments,  # ✅ CORRIGIDO: alinhado com DTO
                "processing_time": response.processing_time
            }
        )
        
        return response
    
    # v2.1: Ordem de exceptions corrigida - mais específicas primeiro
    except AudioTooLongError as e:
        logger.warning(
            "❌ Audio too long",
            extra={
                "request_id": request_id,
                "duration": e.duration,
                "max_duration": e.max_duration,
                "url": request_dto.youtube_url
            }
        )
        raise_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type="AudioTooLongError",
            message=str(e),
            request_id=request_id,
            details={
                "duration": e.duration,
                "max_duration": e.max_duration
            }
        )
    
    # v2.2: Circuit Breaker protection
    except CircuitBreakerOpenError as e:
        logger.warning(
            "⚡ Circuit breaker is open - YouTube API temporarily unavailable",
            extra={
                "request_id": request_id,
                "circuit_name": e.circuit_name,
                "url": request_dto.youtube_url
            }
        )
        raise_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_type="ServiceTemporarilyUnavailable",
            message=f"YouTube API is temporarily unavailable. Circuit breaker '{e.circuit_name}' is open. Please try again later.", # pylint: disable=line-too-long
            request_id=request_id,
            details={"retry_after_seconds": 60}
        )
    
    except AudioCorruptedError as e:
        logger.error(
            "❌ Audio corrupted",
            extra={
                "request_id": request_id,
                "file_path": e.file_path,
                "reason": e.reason
            }
        )
        raise_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type="AudioCorruptedError",
            message=str(e),
            request_id=request_id,
            details={"file_path": e.file_path, "reason": e.reason}
        )
    
    except ValidationError as e:
        logger.warning(
            "❌ Validation error",
            extra={
                "request_id": request_id,
                "error": str(e),
                "url": request_dto.youtube_url
            }
        )
        raise_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type="ValidationError",
            message=str(e),
            request_id=request_id,
            details={"url": request_dto.youtube_url}
        )
    
    except OperationTimeoutError as e:
        logger.error(
            "🔥 Operation timeout",
            extra={
                "request_id": request_id,
                "operation": e.operation,
                "timeout": e.timeout
            }
        )
        raise_error(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            error_type="OperationTimeoutError",
            message=str(e),
            request_id=request_id,
            details={
                "operation": e.operation,
                "timeout_seconds": e.timeout
            }
        )
    
    except (VideoDownloadError, NetworkError) as e:
        logger.error(
            "🔥 Download/Network error",
            extra={
                "request_id": request_id,
                "error_type": type(e).__name__,
                "error": str(e),
                "url": request_dto.youtube_url
            }
        )
        raise_error(
            status_code=status.HTTP_404_NOT_FOUND,
            error_type=type(e).__name__,
            message=str(e),
            request_id=request_id,
            details={"url": request_dto.youtube_url}
        )
    
    except TranscriptionError as e:
        logger.error(
            "🔥 Transcription error",
            extra={
                "request_id": request_id,
                "error": str(e)
            },
            exc_info=True
        )
        raise_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_type="TranscriptionError",
            message=str(e),
            request_id=request_id
        )
    
    except Exception as e:
        logger.critical(
            "🔥🔥 Unexpected error in transcription endpoint",
            extra={
                "request_id": request_id,
                "error_type": type(e).__name__,
                "error": str(e),
                "url": request_dto.youtube_url
            },
            exc_info=True
        )
        raise_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_type="InternalServerError",
            message="An unexpected error occurred during transcription",
            request_id=request_id
        )

