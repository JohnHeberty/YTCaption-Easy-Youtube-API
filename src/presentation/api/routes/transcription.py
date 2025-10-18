"""
Rotas de transcrição.
Endpoints para transcrição de vídeos do YouTube.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from src.application.use_cases import TranscribeYouTubeVideoUseCase
from src.application.dtos import (
    TranscribeRequestDTO,
    TranscribeResponseDTO,
    ErrorResponseDTO
)
from src.domain.exceptions import (
    VideoDownloadError,
    TranscriptionError,
    ValidationError
)
from src.presentation.api.dependencies import get_transcribe_use_case


router = APIRouter(prefix="/api/v1/transcribe", tags=["Transcription"])


@router.post(
    "",
    response_model=TranscribeResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Transcribe YouTube video",
    description="Downloads a YouTube video and transcribes its audio using Whisper",
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
        500: {
            "description": "Server error",
            "model": ErrorResponseDTO
        }
    }
)
async def transcribe_video(
    request: TranscribeRequestDTO,
    use_case: TranscribeYouTubeVideoUseCase = Depends(get_transcribe_use_case)
) -> TranscribeResponseDTO:
    """
    Transcreve um vídeo do YouTube.
    
    - **youtube_url**: URL completa do vídeo do YouTube
    - **language**: Código do idioma (opcional, 'auto' para detecção automática)
    
    Retorna a transcrição completa com segmentos timestampados.
    """
    try:
        logger.info(f"Received transcription request: {request.youtube_url}")
        
        response = await use_case.execute(request)
        
        logger.info(f"Transcription successful: {response.transcription_id}")
        return response
        
    except ValidationError as e:
        logger.warning(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": str(e),
                "details": {"url": request.youtube_url}
            }
        )
    
    except VideoDownloadError as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "VideoDownloadError",
                "message": str(e),
                "details": {"url": request.youtube_url}
            }
        )
    
    except TranscriptionError as e:
        logger.error(f"Transcription error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "TranscriptionError",
                "message": str(e)
            }
        )
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalServerError",
                "message": "An unexpected error occurred"
            }
        )
