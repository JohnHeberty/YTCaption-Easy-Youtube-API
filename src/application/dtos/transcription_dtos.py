"""
DTOs (Data Transfer Objects) para a camada de aplicação.
Seguem o princípio de separação de responsabilidades.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl, validator


class TranscribeRequestDTO(BaseModel):
    """DTO para requisição de transcrição."""
    
    youtube_url: str = Field(
        ...,
        description="URL do vídeo do YouTube",
        examples=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]
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
                "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "video_id": "dQw4w9WgXcQ",
                "language": "en",
                "full_text": "Never gonna give you up...",
                "segments": [
                    {
                        "text": "Never gonna give you up",
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
    """DTO para respostas de erro."""
    
    error: str = Field(..., description="Tipo de erro")
    message: str = Field(..., description="Mensagem de erro")
    details: Optional[dict] = Field(None, description="Detalhes adicionais")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "VideoDownloadError",
                "message": "Failed to download video",
                "details": {
                    "url": "https://youtube.com/watch?v=invalid",
                    "reason": "Video not found"
                }
            }
        }
