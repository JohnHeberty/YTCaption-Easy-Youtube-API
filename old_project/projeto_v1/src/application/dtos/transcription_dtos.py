"""
DTOs (Data Transfer Objects) para a camada de aplicação.
Seguem o princípio de separação de responsabilidades.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl, validator


class TranscribeRequestDTO(BaseModel):
    """DTO para requisição de transcrição."""
    
    youtube_url: str = Field(
        ...,
        description="URL do vídeo do YouTube",
        examples=["https://www.youtube.com/watch?v=hmQKOoSXnLk"]
    )
    language: Optional[str] = Field(
        default="auto",
        description="Código do idioma (auto para detecção automática)",
        examples=["auto", "en", "pt", "es"]
    )
    use_youtube_transcript: bool = Field(
        default=False,
        description="Se True, usa legendas do YouTube ao invés do Whisper (mais rápido)"
    )
    prefer_manual_subtitles: bool = Field(
        default=True,
        description="Se True, prefere legendas manuais sobre automáticas (apenas quando use_youtube_transcript=True)"
    )
    
    @validator('youtube_url')
    def validate_youtube_url(cls, v: str) -> str:
        """Valida se é uma URL do YouTube."""
        if not any(domain in v.lower() for domain in ['youtube.com', 'youtu.be']):
            raise ValueError("Must be a valid YouTube URL")
        return v


class TranscriptionSegmentDTO(BaseModel):
    """DTO para segmento de transcrição."""
    
    text: str = Field(..., description="Texto do segmento")
    start: float = Field(..., description="Tempo inicial em segundos", ge=0)
    end: float = Field(..., description="Tempo final em segundos", ge=0)
    duration: float = Field(..., description="Duração do segmento em segundos", ge=0)


class TranscribeResponseDTO(BaseModel):
    """DTO para resposta de transcrição."""
    
    transcription_id: str = Field(..., description="ID único da transcrição")
    youtube_url: str = Field(..., description="URL do vídeo")
    video_id: str = Field(..., description="ID do vídeo no YouTube")
    language: str = Field(..., description="Idioma detectado")
    full_text: str = Field(..., description="Texto completo da transcrição")
    segments: List[TranscriptionSegmentDTO] = Field(
        ...,
        description="Lista de segmentos com timestamps"
    )
    total_segments: int = Field(..., description="Número total de segmentos")
    duration: float = Field(..., description="Duração total em segundos")
    processing_time: Optional[float] = Field(
        None,
        description="Tempo de processamento em segundos"
    )
    source: str = Field(
        default="whisper",
        description="Fonte da transcrição (whisper ou youtube_transcript)"
    )
    transcript_type: Optional[str] = Field(
        None,
        description="Tipo de transcrição do YouTube (manual/auto), se aplicável"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "transcription_id": "123e4567-e89b-12d3-a456-426614174000",
                "youtube_url": "https://www.youtube.com/watch?v=hmQKOoSXnLk",
                "video_id": "hmQKOoSXnLk",
                "language": "en",
                "full_text": "Welcome to this tutorial...",
                "segments": [
                    {
                        "text": "Welcome to this tutorial",
                        "start": 0.0,
                        "end": 2.5,
                        "duration": 2.5
                    }
                ],
                "total_segments": 1,
                "duration": 2.5,
                "processing_time": 15.3,
                "source": "whisper",
                "transcript_type": None
            }
        }


class CaptionFormat(str):
    """Enum para formatos de legenda."""
    SRT = "srt"
    VTT = "vtt"
    JSON = "json"


class ExportCaptionsRequestDTO(BaseModel):
    """DTO para requisição de exportação de legendas."""
    
    format: str = Field(
        default="srt",
        description="Formato da legenda",
        pattern="^(srt|vtt|json)$"
    )


class HealthCheckDTO(BaseModel):
    """DTO para health check."""
    
    status: str = Field(..., description="Status da API")
    version: str = Field(..., description="Versão da API")
    whisper_model: str = Field(..., description="Modelo Whisper em uso")
    storage_usage: dict = Field(..., description="Uso de armazenamento")
    uptime_seconds: float = Field(..., description="Tempo de atividade em segundos")


class ErrorResponseDTO(BaseModel):
    """DTO padronizado para respostas de erro."""
    
    error: str = Field(..., description="Tipo/classe do erro")
    message: str = Field(..., description="Mensagem legível do erro")
    request_id: str = Field(..., description="ID da requisição para tracking")
    details: Optional[Dict[str, Any]] = Field(None, description="Detalhes adicionais do erro")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "AudioTooLongError",
                "message": "Audio duration (7250s) exceeds maximum allowed (7200s)",
                "request_id": "abc-123-def-456",
                "details": {
                    "duration": 7250,
                    "max_duration": 7200
                }
            }
        }


class SubtitlesInfoDTO(BaseModel):
    """DTO para informações de legendas disponíveis."""
    
    available: List[str] = Field(..., description="Todas as legendas disponíveis")
    manual_languages: List[str] = Field(..., description="Idiomas com legendas manuais")
    auto_languages: List[str] = Field(..., description="Idiomas com legendas automáticas")
    total: int = Field(..., description="Total de legendas disponíveis")


class LanguageDetectionDTO(BaseModel):
    """DTO para resultado da detecção de idioma."""
    
    detected_language: Optional[str] = Field(None, description="Idioma detectado")
    confidence: Optional[float] = Field(None, description="Confiança da detecção (0-1)")
    method: Optional[str] = Field(None, description="Método de detecção usado")


class WhisperRecommendationDTO(BaseModel):
    """DTO para recomendação de uso do Whisper vs YouTube."""
    
    should_use_youtube_transcript: bool = Field(..., description="Se deve usar transcrição do YouTube")
    reason: str = Field(..., description="Razão da recomendação")
    estimated_time_whisper: Optional[float] = Field(None, description="Tempo estimado com Whisper (segundos)")
    estimated_time_youtube: Optional[float] = Field(None, description="Tempo estimado com YouTube (segundos)")


class VideoInfoResponseDTO(BaseModel):
    """DTO para resposta de informações do vídeo."""
    
    video_id: str = Field(..., description="ID do vídeo no YouTube")
    title: str = Field(..., description="Título do vídeo")
    duration_seconds: int = Field(..., description="Duração em segundos")
    duration_formatted: str = Field(..., description="Duração formatada (HH:MM:SS)")
    uploader: Optional[str] = Field(None, description="Nome do canal/uploader")
    upload_date: Optional[str] = Field(None, description="Data de upload (YYYYMMDD)")
    view_count: Optional[int] = Field(None, description="Número de visualizações")
    description_preview: str = Field(..., description="Prévia da descrição (200 caracteres)")
    language_detection: Optional[LanguageDetectionDTO] = Field(None, description="Detecção de idioma")
    subtitles: SubtitlesInfoDTO = Field(..., description="Informações de legendas")
    whisper_recommendation: Optional[WhisperRecommendationDTO] = Field(None, description="Recomendações Whisper")
    warnings: List[str] = Field(default_factory=list, description="Avisos sobre o vídeo")
    
    class Config:
        json_schema_extra = {
            "example": {
                "video_id": "hmQKOoSXnLk",
                "title": "Sample Tutorial Video",
                "duration_seconds": 180,
                "duration_formatted": "00:03:00",
                "uploader": "Tutorial Channel",
                "upload_date": "20231015",
                "view_count": 50000,
                "description_preview": "A comprehensive tutorial on...",
                "language_detection": {
                    "detected_language": "en",
                    "confidence": 0.95,
                    "method": "metadata"
                },
                "subtitles": {
                    "available": ["en", "es", "pt"],
                    "manual_languages": ["en"],
                    "auto_languages": ["es", "pt"],
                    "total": 3
                },
                "whisper_recommendation": {
                    "should_use_youtube_transcript": True,
                    "reason": "Manual subtitles available in detected language",
                    "estimated_time_whisper": 45.0,
                    "estimated_time_youtube": 2.0
                },
                "warnings": []
            }
        }


class ReadinessCheckDTO(BaseModel):
    """DTO para resposta de verificação de prontidão."""
    
    status: str = Field(..., description="Status de prontidão (ready/not_ready)")
    checks: Dict[str, bool] = Field(..., description="Status de cada verificação")
    message: Optional[str] = Field(None, description="Mensagem adicional")
    timestamp: float = Field(..., description="Timestamp da verificação")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "ready",
                "checks": {
                    "storage": True,
                    "whisper_model": True,
                    "worker_pool": True
                },
                "message": "All systems operational",
                "timestamp": 1234567890.123
            }
        }


class UploadVideoRequestDTO(BaseModel):
    """DTO para requisição de transcrição de vídeo enviado."""
    
    language: Optional[str] = Field(
        default=None,
        description="Código do idioma (None para detecção automática)",
        examples=[None, "en", "pt", "es", "fr"]
    )
    model_size: str = Field(
        default="base",
        description="Tamanho do modelo Whisper",
        pattern="^(tiny|base|small|medium|large)$"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "language": "en",
                "model_size": "base"
            }
        }


class UploadVideoResponseDTO(BaseModel):
    """DTO para resposta de transcrição de vídeo enviado."""
    
    transcription_id: str = Field(..., description="ID único da transcrição")
    original_filename: str = Field(..., description="Nome original do arquivo")
    file_format: str = Field(..., description="Formato do arquivo (extensão)")
    file_type: str = Field(..., description="Tipo do arquivo (video ou audio)")
    file_size_bytes: int = Field(..., description="Tamanho do arquivo em bytes")
    duration_seconds: Optional[float] = Field(None, description="Duração do vídeo/áudio em segundos")
    language: str = Field(..., description="Idioma detectado/especificado")
    model_size: str = Field(..., description="Tamanho do modelo Whisper usado")
    full_text: str = Field(..., description="Texto completo da transcrição")
    segments: List[TranscriptionSegmentDTO] = Field(
        ...,
        description="Lista de segmentos com timestamps"
    )
    total_segments: int = Field(..., description="Número total de segmentos")
    processing_time_seconds: float = Field(..., description="Tempo de processamento em segundos")
    metadata: Dict[str, Any] = Field(..., description="Metadados adicionais do arquivo")
    
    class Config:
        json_schema_extra = {
            "example": {
                "transcription_id": "123e4567-e89b-12d3-a456-426614174000",
                "original_filename": "my_video.mp4",
                "file_format": "mp4",
                "file_type": "video",
                "file_size_bytes": 52428800,
                "duration_seconds": 120.5,
                "language": "en",
                "model_size": "base",
                "full_text": "Welcome to this tutorial...",
                "segments": [
                    {
                        "text": "Welcome to this tutorial",
                        "start": 0.0,
                        "end": 2.5,
                        "duration": 2.5
                    }
                ],
                "total_segments": 48,
                "processing_time_seconds": 25.3,
                "metadata": {
                    "has_video": True,
                    "has_audio": True,
                    "video_codec": "h264",
                    "audio_codec": "aac"
                }
            }
        }


class SupportedFormatsResponseDTO(BaseModel):
    """DTO para resposta de formatos suportados."""
    
    video_formats: List[str] = Field(..., description="Formatos de vídeo suportados")
    audio_formats: List[str] = Field(..., description="Formatos de áudio suportados")
    all_formats: List[str] = Field(..., description="Todos os formatos suportados")
    total: int = Field(..., description="Total de formatos suportados")
    max_file_size_mb: float = Field(..., description="Tamanho máximo de arquivo (MB)")
    max_duration_seconds: int = Field(..., description="Duração máxima (segundos)")
    max_duration_formatted: str = Field(..., description="Duração máxima formatada (HH:MM:SS)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "video_formats": ["mp4", "avi", "mov", "mkv", "flv", "wmv", "webm", "mpg", "mpeg", "m4v", "3gp"],
                "audio_formats": ["mp3", "wav", "aac", "flac", "ogg", "m4a", "wma", "opus"],
                "all_formats": ["mp4", "avi", "mov", "mkv", "mp3", "wav", "..."],
                "total": 19,
                "max_file_size_mb": 2500.0,
                "max_duration_seconds": 10800,
                "max_duration_formatted": "03:00:00"
            }
        }
