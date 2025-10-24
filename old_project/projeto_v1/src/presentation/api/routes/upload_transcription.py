"""
Rotas para upload e transcrição de vídeos.
"""
import logging
import uuid
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.application.dtos.transcription_dtos import (
    UploadVideoRequestDTO,
    UploadVideoResponseDTO,
    SupportedFormatsResponseDTO,
    ErrorResponseDTO,
    TranscriptionSegmentDTO
)
from src.application.use_cases.transcribe_uploaded_video import TranscribeUploadedVideoUseCase
from src.domain.exceptions import (
    VideoUploadError,
    UnsupportedFormatError,
    FileTooLargeError,
    InvalidVideoFileError,
    TranscriptionError
)
from src.infrastructure.storage.video_upload_service import VideoUploadService
from src.presentation.api.dependencies import (
    get_transcription_service,
    get_storage_service,
    get_upload_validator
)

logger = logging.getLogger(__name__)

# Rate limiter (2 uploads por minuto)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(
    prefix="/upload",
    tags=["Upload Transcription"]
)


def get_upload_service(storage_service = Depends(get_storage_service)):
    """Dependência para serviço de upload."""
    return VideoUploadService(storage_service)


def get_transcribe_upload_use_case(
    transcription_service = Depends(get_transcription_service),
    storage_service = Depends(get_storage_service),
    upload_validator = Depends(get_upload_validator)
):
    """Dependência para caso de uso de transcrição de upload."""
    return TranscribeUploadedVideoUseCase(
        transcription_service,
        storage_service,
        upload_validator
    )


@router.post(
    "",
    response_model=UploadVideoResponseDTO,
    status_code=200,
    summary="Transcrever vídeo enviado",
    description="""
    Envia um arquivo de vídeo ou áudio para transcrição com Whisper AI.
    
    **Formatos suportados:**
    - Vídeo: MP4, AVI, MOV, MKV, FLV, WMV, WebM, MPG, MPEG, M4V, 3GP
    - Áudio: MP3, WAV, AAC, FLAC, OGG, M4A, WMA, OPUS
    
    **Limites:**
    - Tamanho máximo: 2.5GB
    - Duração máxima: 3 horas (10800 segundos)
    - Rate limit: 2 uploads por minuto
    
    **Processo:**
    1. Upload do arquivo (streaming em chunks)
    2. Validação (formato, tamanho, duração via FFprobe)
    3. Extração de áudio (se for vídeo)
    4. Transcrição com Whisper
    5. Retorno da transcrição + metadados
    6. Cleanup automático de arquivos temporários
    """
)
@limiter.limit("2/minute")
async def transcribe_upload(
    file: UploadFile = File(
        ...,
        description="Arquivo de vídeo ou áudio para transcrever"
    ),
    language: Optional[str] = Form(
        None,
        description="Código do idioma (None = auto-detect)",
        example="en"
    ),
    model_size: str = Form(
        "base",
        description="Tamanho do modelo Whisper",
        pattern="^(tiny|base|small|medium|large)$"
    ),
    upload_service: VideoUploadService = Depends(get_upload_service),
    use_case: TranscribeUploadedVideoUseCase = Depends(get_transcribe_upload_use_case)
):
    """
    Transcreve arquivo de vídeo/áudio enviado.
    
    Args:
        file: Arquivo enviado
        language: Idioma (None = auto-detect)
        model_size: Tamanho do modelo Whisper
        upload_service: Serviço de upload
        use_case: Caso de uso de transcrição
    
    Returns:
        UploadVideoResponseDTO: Transcrição + metadados
    
    Raises:
        HTTPException: Erros de validação ou transcrição
    """
    request_id = str(uuid.uuid4())
    
    try:
        logger.info(
            f"Upload transcription request [{request_id}]: "
            f"file={file.filename}, language={language}, model={model_size}"
        )
        
        # 1. Salvar arquivo (streaming)
        uploaded_file = await upload_service.save_upload(file)
        
        logger.info(
            f"File saved [{request_id}]: "
            f"path={uploaded_file.file_path}, size={uploaded_file.get_size_mb():.2f}MB"
        )
        
        # 2. Executar transcrição
        result = await use_case.execute(
            uploaded_file=uploaded_file,
            model_size=model_size,
            language=language
        )
        
        # 3. Construir resposta
        transcription_data = result['transcription']
        metadata = result['metadata']
        
        segments = [
            TranscriptionSegmentDTO(
                text=seg['text'],
                start=seg['start'],
                end=seg['end'],
                duration=seg['end'] - seg['start']
            )
            for seg in transcription_data.get('segments', [])
        ]
        
        response = UploadVideoResponseDTO(
            transcription_id=request_id,
            original_filename=metadata['original_filename'],
            file_format=metadata['format'],
            file_type=metadata['type'],
            file_size_bytes=metadata['file_size_bytes'],
            duration_seconds=metadata.get('duration_seconds'),
            language=transcription_data.get('language', language or 'auto-detect'),
            model_size=model_size,
            full_text=transcription_data.get('text', ''),
            segments=segments,
            total_segments=len(segments),
            processing_time_seconds=metadata['processing_time_seconds'],
            metadata={
                'has_video': metadata.get('has_video', False),
                'has_audio': metadata.get('has_audio', False),
                'video_codec': metadata.get('video_codec'),
                'audio_codec': metadata.get('audio_codec')
            }
        )
        
        logger.info(
            f"Upload transcription completed [{request_id}]: "
            f"{len(segments)} segments, {metadata['processing_time_seconds']:.2f}s"
        )
        
        return response
    
    except UnsupportedFormatError as e:
        logger.warning(f"Unsupported format [{request_id}]: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "UnsupportedFormatError",
                "message": str(e),
                "request_id": request_id,
                "details": {
                    "format": e.format,
                    "supported_formats": e.supported_formats
                }
            }
        )
    
    except FileTooLargeError as e:
        logger.warning(f"File too large [{request_id}]: {e}")
        raise HTTPException(
            status_code=413,
            detail={
                "error": "FileTooLargeError",
                "message": str(e),
                "request_id": request_id,
                "details": {
                    "size_mb": e.size_mb,
                    "max_size_mb": e.max_size_mb
                }
            }
        )
    
    except InvalidVideoFileError as e:
        logger.warning(f"Invalid video file [{request_id}]: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "InvalidVideoFileError",
                "message": str(e),
                "request_id": request_id,
                "details": {
                    "reason": e.reason
                }
            }
        )
    
    except VideoUploadError as e:
        logger.error(f"Video upload error [{request_id}]: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "VideoUploadError",
                "message": str(e),
                "request_id": request_id
            }
        )
    
    except TranscriptionError as e:
        logger.error(f"Transcription error [{request_id}]: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "TranscriptionError",
                "message": str(e),
                "request_id": request_id
            }
        )
    
    except Exception as e:
        logger.exception(f"Unexpected error [{request_id}]: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "InternalServerError",
                "message": "An unexpected error occurred during transcription",
                "request_id": request_id
            }
        )


@router.get(
    "/formats",
    response_model=SupportedFormatsResponseDTO,
    status_code=200,
    summary="Listar formatos suportados",
    description="Retorna lista de todos os formatos de vídeo e áudio suportados para upload."
)
async def get_supported_formats(
    upload_validator = Depends(get_upload_validator)
):
    """
    Lista formatos suportados e limites de upload.
    
    Args:
        upload_validator: Validador de upload
    
    Returns:
        SupportedFormatsResponseDTO: Formatos e limites
    """
    try:
        formats = await upload_validator.get_supported_formats()
        
        video_formats = formats.get('video', [])
        audio_formats = formats.get('audio', [])
        all_formats = video_formats + audio_formats
        
        # Limites padrão
        max_size_mb = 2500.0
        max_duration_seconds = 10800  # 3 horas
        
        # Formatar duração (HH:MM:SS)
        hours = max_duration_seconds // 3600
        minutes = (max_duration_seconds % 3600) // 60
        seconds = max_duration_seconds % 60
        max_duration_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        return SupportedFormatsResponseDTO(
            video_formats=sorted(video_formats),
            audio_formats=sorted(audio_formats),
            all_formats=sorted(all_formats),
            total=len(all_formats),
            max_file_size_mb=max_size_mb,
            max_duration_seconds=max_duration_seconds,
            max_duration_formatted=max_duration_formatted
        )
    
    except Exception as e:
        logger.exception(f"Error getting supported formats: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "InternalServerError",
                "message": "Failed to retrieve supported formats"
            }
        )
