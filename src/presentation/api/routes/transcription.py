"""
Rotas de transcrição.
Endpoints para transcrição de vídeos do YouTube.

v2.1: Rate limiting para prevenir abuso.
v2.2: Circuit breaker para proteção contra falhas em cascata.
"""
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
from src.presentation.api.dependencies import get_transcribe_use_case


router = APIRouter(prefix="/api/v1/transcribe", tags=["Transcription"])

# Rate limiter instance
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "",
    response_model=TranscribeResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Transcribe YouTube video",
    description="""
    Downloads a YouTube video and transcribes its audio using Whisper.
    
    **Rate Limit**: 5 requests per minute per IP address.
    
    **Timeout**: Automatic timeout based on video duration.
    """,
    responses={
        200: {
            "description": "Successful transcription",
            "model": TranscribeResponseDTO
        },
        400: {
            "description": "Invalid request",
            "model": ErrorResponseDTO
        },
        404: {
            "description": "Video not found",
            "model": ErrorResponseDTO
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "RateLimitExceeded",
                        "message": "Rate limit exceeded: 5 per 1 minute"
                    }
                }
            }
        },
        500: {
            "description": "Server error",
            "model": ErrorResponseDTO
        }
    }
)
@limiter.limit("5/minute")  # v2.1: Rate limiting
async def transcribe_video(
    request: Request,  # ✅ CORRIGIDO: Primeiro parâmetro deve ser Request
    request_dto: TranscribeRequestDTO,  # ✅ Renomeado para request_dto
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
                "segments_count": response.total_segments,
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "AudioTooLongError",
                "message": str(e),
                "request_id": request_id,
                "details": {
                    "duration": e.duration,
                    "max_duration": e.max_duration
                }
            }
        ) from e
    
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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "ServiceTemporarilyUnavailable",
                "message": f"YouTube API is temporarily unavailable. Circuit breaker '{e.circuit_name}' is open. Please try again later.",
                "request_id": request_id,
                "retry_after_seconds": 60
            }
        ) from e
    
    except AudioCorruptedError as e:
        logger.error(
            "❌ Audio corrupted",
            extra={
                "request_id": request_id,
                "file_path": e.file_path,
                "reason": e.reason
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "AudioCorruptedError",
                "message": str(e),
                "request_id": request_id
            }
        ) from e
    
    except ValidationError as e:
        logger.warning(
            "❌ Validation error",
            extra={
                "request_id": request_id,
                "error": str(e),
                "url": request_dto.youtube_url
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": str(e),
                "request_id": request_id,
                "details": {"url": request_dto.youtube_url}
            }
        ) from e
    
    except OperationTimeoutError as e:
        logger.error(
            "🔥 Operation timeout",
            extra={
                "request_id": request_id,
                "operation": e.operation,
                "timeout": e.timeout
            }
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error": "OperationTimeoutError",
                "message": str(e),
                "request_id": request_id,
                "details": {
                    "operation": e.operation,
                    "timeout_seconds": e.timeout
                }
            }
        ) from e
    
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": type(e).__name__,
                "message": str(e),
                "request_id": request_id,
                "details": {"url": request_dto.youtube_url}
            }
        ) from e
    
    except TranscriptionError as e:
        logger.error(
            "🔥 Transcription error",
            extra={
                "request_id": request_id,
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "TranscriptionError",
                "message": str(e),
                "request_id": request_id
            }
        ) from e
    
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalServerError",
                "message": "An unexpected error occurred",
                "request_id": request_id
            }
        ) from e
