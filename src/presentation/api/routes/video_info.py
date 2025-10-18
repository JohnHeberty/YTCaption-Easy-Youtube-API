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
    Obtém informações completas do vídeo sem baixá-lo.
    Inclui detecção de idioma e legendas disponíveis.
    
    Args:
        request: Requisição com URL do YouTube
        
    Returns:
        Informações completas do vídeo incluindo:
        - Duração e tempo estimado de processamento
        - Detecção de idioma com nível de confiança
        - Legendas disponíveis (manuais e automáticas)
        - Recomendações de modelo Whisper
        
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
        
        # Obter informações completas com detecção de idioma
        info = await downloader.get_video_info_with_language(youtube_url)
        
        duration = info.get('duration', 0)
        
        # Formatar duração
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        duration_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
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
            "language_detection": info.get('language_detection', {}),
            "subtitles": {
                "available": info.get('available_subtitles', []),
                "manual_languages": info.get('subtitle_languages', []),
                "auto_languages": info.get('auto_caption_languages', []),
                "total": len(info.get('available_subtitles', []))
            },
            "whisper_recommendation": info.get('whisper_recommendation', {}),
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
        
        # Avisos sobre legendas
        subtitles_info = response["subtitles"]
        if subtitles_info["total"] > 0:
            if len(subtitles_info["manual_languages"]) > 0:
                response["warnings"].append(
                    f"Manual subtitles available in {len(subtitles_info['manual_languages'])} languages. "
                    "You can use YouTube transcripts instead of Whisper for faster results."
                )
            else:
                response["warnings"].append(
                    f"Auto-generated captions available in {len(subtitles_info['auto_languages'])} languages. "
                    "You can use them for faster results, but quality may vary."
                )
        
        logger.info(
            f"Video info retrieved: {youtube_url.video_id}, "
            f"duration={duration}s, "
            f"detected_lang={info.get('language_detection', {}).get('detected_language')}, "
            f"subtitles={subtitles_info['total']}"
        )
        
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
