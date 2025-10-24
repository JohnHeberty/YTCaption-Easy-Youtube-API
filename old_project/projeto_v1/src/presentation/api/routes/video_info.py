"""
Video Info Routes - Endpoint para obter informações do vídeo antes de transcrever.

v2.1: Rate limiting e melhorias de exception handling.
v2.2: Circuit breaker para proteção contra falhas em cascata.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from loguru import logger

from src.application.dtos import (
    TranscribeRequestDTO,
    VideoInfoResponseDTO,
    LanguageDetectionDTO,
    SubtitlesInfoDTO,
    WhisperRecommendationDTO,
    ErrorResponseDTO
)
from src.domain.value_objects import YouTubeURL
from src.domain.exceptions import VideoDownloadError, NetworkError
from src.domain.interfaces import IVideoDownloader
from src.infrastructure.utils import CircuitBreakerOpenError
from src.presentation.api.dependencies import Container, raise_error


router = APIRouter(prefix="/api/v1", tags=["video-info"])

# Rate limiter instance
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/video/info",
    response_model=VideoInfoResponseDTO,
    status_code=200,
    summary="Get video information without downloading",
    description="""
    Get complete video metadata without downloading the audio.
    
    **⚡ Rate Limit:** 10 requests per minute per IP address
    
    Returns detailed information including:
    - Video duration and metadata
    - Language detection with confidence score
    - Available subtitles (manual and auto-generated)
    - Whisper model recommendations
    - Processing time estimates
    
    If rate limit is exceeded, returns HTTP 429.
    """,
    responses={
        200: {
            "description": "Video information retrieved successfully",
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
            "model": ErrorResponseDTO,
            "description": "Invalid YouTube URL"
        },
        404: {
            "model": ErrorResponseDTO,
            "description": "Video not found or unavailable"
        },
        429: {
            "model": ErrorResponseDTO,
            "description": "Rate limit exceeded - 10 requests per minute per IP"
        },
        500: {
            "model": ErrorResponseDTO,
            "description": "Internal server error"
        }
    }
)
@limiter.limit("10/minute")
async def get_video_info(
    request: Request,
    request_dto: TranscribeRequestDTO,
    downloader: IVideoDownloader = Depends(Container.get_video_downloader)
) -> VideoInfoResponseDTO:
    """
    Obtém informações completas do vídeo sem baixá-lo.
    Inclui detecção de idioma e legendas disponíveis.
    
    Args:
        request: FastAPI Request object
        request_dto: Requisição com URL do YouTube
        downloader: Video downloader service
        
    Returns:
        VideoInfoResponseDTO: Informações completas do vídeo
        
    Raises:
        HTTPException: Se houver erro ao obter informações
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        logger.info(
            "Getting video info",
            extra={
                "request_id": request_id,
                "youtube_url": request_dto.youtube_url,
                "client_ip": request.client.host if request.client else "unknown"
            }
        )
        
        # Validar URL
        try:
            youtube_url = YouTubeURL.create(request_dto.youtube_url)
        except ValueError as e:
            logger.warning(
                "Invalid YouTube URL",
                extra={
                    "request_id": request_id,
                    "url": request_dto.youtube_url,
                    "error": str(e)
                }
            )
            raise_error(
                status_code=400,
                error_type="ValidationError",
                message=f"Invalid YouTube URL: {str(e)}",
                request_id=request_id
            )
        
        # Obter informações completas com detecção de idioma
        info = await downloader.get_video_info_with_language(youtube_url)
        
        duration = info.get('duration', 0)
        
        # Formatar duração
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        duration_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # Preparar descrição
        description = info.get('description', '')
        description_preview = (
            description[:200] + "..." if description and len(description) > 200 
            else description if description else ""
        )
        
        # Preparar avisos
        warnings = []
        
        # Adicionar avisos baseados na duração
        if duration > 7200:  # 2 horas
            warnings.append(
                "Video is very long (>2h). Processing may take significant time. "
                "Consider using 'tiny' or 'base' model for faster results."
            )
        elif duration > 3600:  # 1 hora
            warnings.append(
                "Video is long (>1h). Processing may take 20-30 minutes with 'base' model."
            )
        
        if duration > 10800:  # 3 horas
            warnings.append(
                "Video exceeds recommended maximum duration (3h). "
                "Processing may fail or timeout. Consider processing shorter videos."
            )
        
        # Informações de legendas
        available_subtitles = info.get('available_subtitles', [])
        subtitle_languages = info.get('subtitle_languages', [])
        auto_caption_languages = info.get('auto_caption_languages', [])
        
        # Avisos sobre legendas
        if len(available_subtitles) > 0:
            if len(subtitle_languages) > 0:
                warnings.append(
                    f"Manual subtitles available in {len(subtitle_languages)} languages. "
                    "You can use YouTube transcripts instead of Whisper for faster results."
                )
            else:
                warnings.append(
                    f"Auto-generated captions available in {len(auto_caption_languages)} languages. "
                    "You can use them for faster results, but quality may vary."
                )
        
        # Construir DTOs
        subtitles_dto = SubtitlesInfoDTO(
            available=available_subtitles,
            manual_languages=subtitle_languages,
            auto_languages=auto_caption_languages,
            total=len(available_subtitles)
        )
        
        # Language detection DTO (opcional)
        language_detection_dto = None
        if info.get('language_detection'):
            lang_det = info.get('language_detection')
            language_detection_dto = LanguageDetectionDTO(
                detected_language=lang_det.get('detected_language'),
                confidence=lang_det.get('confidence'),
                method=lang_det.get('method')
            )
        
        # Whisper recommendation DTO (opcional)
        whisper_recommendation_dto = None
        if info.get('whisper_recommendation'):
            whisper_rec = info.get('whisper_recommendation')
            whisper_recommendation_dto = WhisperRecommendationDTO(
                should_use_youtube_transcript=whisper_rec.get('should_use_youtube_transcript', False),
                reason=whisper_rec.get('reason', ''),
                estimated_time_whisper=whisper_rec.get('estimated_time_whisper'),
                estimated_time_youtube=whisper_rec.get('estimated_time_youtube')
            )
        
        # Construir response DTO
        response_dto = VideoInfoResponseDTO(
            video_id=info.get('video_id', ''),
            title=info.get('title', ''),
            duration_seconds=duration,
            duration_formatted=duration_formatted,
            uploader=info.get('uploader'),
            upload_date=info.get('upload_date'),
            view_count=info.get('view_count'),
            description_preview=description_preview,
            language_detection=language_detection_dto,
            subtitles=subtitles_dto,
            whisper_recommendation=whisper_recommendation_dto,
            warnings=warnings
        )
        
        logger.info(
            "Video info retrieved successfully",
            extra={
                "request_id": request_id,
                "video_id": youtube_url.video_id,
                "duration": duration,
                "detected_lang": info.get('language_detection', {}).get('detected_language'),
                "subtitles_count": len(available_subtitles)
            }
        )
        
        return response_dto
    
    except HTTPException:
        raise
    
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
            status_code=503,
            error_type="ServiceTemporarilyUnavailable",
            message=f"YouTube API is temporarily unavailable. Circuit breaker '{e.circuit_name}' is open. Please try again later.",
            request_id=request_id,
            details={"retry_after_seconds": 60}
        )
    
    except (VideoDownloadError, NetworkError) as e:
        logger.error(
            "Failed to get video info",
            extra={
                "request_id": request_id,
                "error_type": type(e).__name__,
                "error": str(e),
                "url": request_dto.youtube_url
            },
            exc_info=True
        )
        raise_error(
            status_code=404,
            error_type=type(e).__name__,
            message=str(e),
            request_id=request_id,
            details={"url": request_dto.youtube_url}
        )
    
    except Exception as e:
        logger.critical(
            "Unexpected error getting video info",
            extra={
                "request_id": request_id,
                "error_type": type(e).__name__,
                "error": str(e),
                "url": request_dto.youtube_url
            },
            exc_info=True
        )
        raise_error(
            status_code=500,
            error_type="InternalServerError",
            message="Failed to get video information",
            request_id=request_id
        )
