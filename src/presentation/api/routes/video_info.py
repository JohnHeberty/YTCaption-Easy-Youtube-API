"""
Video Info Routes - Endpoint para obter informações do vídeo antes de transcrever.
"""
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger

from src.application.dtos import TranscribeRequestDTO
from src.domain.value_objects import YouTubeURL
from src.domain.exceptions import VideoDownloadError, ValidationError
from src.domain.interfaces import IVideoDownloader
from src.presentation.api.dependencies import Container


router = APIRouter(prefix="/api/v1", tags=["video-info"])


@router.post("/video/info")
async def get_video_info(
    request: TranscribeRequestDTO,
    downloader: IVideoDownloader = Depends(Container.get_video_downloader)
):
    """
    Obtém informações do vídeo sem baixá-lo.
    Útil para verificar duração antes de iniciar transcrição.
    
    Args:
        request: Requisição com URL do YouTube
        
    Returns:
        Informações do vídeo incluindo duração e tempo estimado de processamento
        
    Raises:
        HTTPException: Se houver erro ao obter informações
    """
    try:
        logger.info(f"Getting video info: {request.youtube_url}")
        
        # Validar URL
        try:
            youtube_url = YouTubeURL.create(request.youtube_url)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "ValidationError",
                    "message": f"Invalid YouTube URL: {str(e)}"
                }
            )
        
        # Obter informações
        info = await downloader.get_video_info(youtube_url)
        
        duration = info.get('duration', 0)
        
        # Calcular tempo estimado de processamento
        # Base model: ~0.5x realtime em CPU
        # Medium model: ~2x realtime em CPU
        estimated_time = {
            'tiny': duration * 0.2,
            'base': duration * 0.5,
            'small': duration * 1.0,
            'medium': duration * 2.0,
            'large': duration * 3.0
        }
        
        # Formatar duração
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        duration_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # Formatar tempos estimados
        estimated_formatted = {}
        for model, time in estimated_time.items():
            est_minutes = int(time // 60)
            est_seconds = int(time % 60)
            estimated_formatted[model] = f"{est_minutes:02d}:{est_seconds:02d}"
        
        response = {
            "video_id": info.get('video_id'),
            "title": info.get('title'),
            "duration_seconds": duration,
            "duration_formatted": duration_formatted,
            "uploader": info.get('uploader'),
            "upload_date": info.get('upload_date'),
            "view_count": info.get('view_count'),
            "description_preview": (
                info.get('description', '')[:200] + "..." 
                if info.get('description') and len(info.get('description', '')) > 200 
                else info.get('description', '')
            ),
            "estimated_processing_time": {
                "seconds": estimated_time,
                "formatted": estimated_formatted
            },
            "warnings": []
        }
        
        # Adicionar avisos baseados na duração
        if duration > 7200:  # 2 horas
            response["warnings"].append(
                "Video is very long (>2h). Processing may take significant time. "
                "Consider using 'tiny' or 'base' model for faster results."
            )
        elif duration > 3600:  # 1 hora
            response["warnings"].append(
                "Video is long (>1h). Processing may take 20-30 minutes with 'base' model."
            )
        
        if duration > 10800:  # 3 horas
            response["warnings"].append(
                "Video exceeds recommended maximum duration (3h). "
                "Processing may fail or timeout. Consider processing shorter videos."
            )
        
        logger.info(f"Video info retrieved: {youtube_url.video_id}, duration={duration}s")
        
        return response
        
    except VideoDownloadError as e:
        logger.error(f"Failed to get video info: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "VideoDownloadError",
                "message": str(e)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting video info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "InternalServerError",
                "message": "Failed to get video information"
            }
        )
