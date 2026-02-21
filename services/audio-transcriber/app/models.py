from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
import hashlib


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class WhisperEngine(str, Enum):
    """
    Engines de transcrição Whisper disponíveis.
    
    - faster-whisper: Padrão. 4x mais rápido, menos VRAM, word timestamps nativos
    - openai-whisper: Original da OpenAI, mais lento mas compatível
    - whisperx: Word-level timestamps com forced alignment (mais preciso)
    """
    FASTER_WHISPER = "faster-whisper"
    OPENAI_WHISPER = "openai-whisper"
    WHISPERX = "whisperx"


class TranscriptionSegment(BaseModel):
    """
    Segmento de transcrição com timestamps.
    Formato compatível com projeto v1.
    """
    text: str = Field(..., description="Texto do segmento transcrito")
    start: float = Field(..., description="Tempo inicial em segundos", ge=0)
    end: float = Field(..., description="Tempo final em segundos", ge=0)
    duration: float = Field(..., description="Duração do segmento em segundos", ge=0)
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Welcome to the show",
                "start": 0.0,
                "end": 2.5,
                "duration": 2.5
            }
        }


class TranscriptionResponse(BaseModel):
    """
    Resposta completa de transcrição.
    Formato compatível com projeto v1.
    """
    transcription_id: str = Field(..., description="ID único da transcrição")
    filename: str = Field(..., description="Nome do arquivo original")
    language: str = Field(..., description="Idioma detectado/especificado (entrada)")
    language_detected: Optional[str] = Field(None, description="Idioma detectado pelo Whisper")
    language_out: Optional[str] = Field(None, description="Idioma de saída (tradução)")
    was_translated: bool = Field(False, description="Se o texto foi traduzido")
    full_text: str = Field(..., description="Texto completo da transcrição")
    segments: List[TranscriptionSegment] = Field(
        ...,
        description="Lista de segmentos com timestamps (start, end, duration)"
    )
    total_segments: int = Field(..., description="Número total de segmentos")
    duration: float = Field(..., description="Duração total do áudio em segundos")
    processing_time: Optional[float] = Field(
        None,
        description="Tempo de processamento em segundos"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "transcription_id": "abc123def456",
                "filename": "audio.mp3",
                "language": "en",
                "full_text": "Welcome to the show. Today we're going to talk about...",
                "segments": [
                    {
                        "text": "Welcome to the show.",
                        "start": 0.0,
                        "end": 2.5,
                        "duration": 2.5
                    },
                    {
                        "text": "Today we're going to talk about...",
                        "start": 2.5,
                        "end": 5.8,
                        "duration": 3.3
                    }
                ],
                "total_segments": 2,
                "duration": 5.8,
                "processing_time": 12.5
            }
        }


class JobRequest(BaseModel):
    operation: Optional[str] = Field(
        default="transcribe",
        description="Operação: transcribe (transcrever) ou translate (traduzir para inglês)"
    )
    language_in: Optional[str] = Field(
        default="auto",
        description="Idioma de entrada: auto (detectar), pt, en, es, etc."
    )
    language_out: Optional[str] = Field(
        default=None,
        description="Idioma de saída para tradução: pt, en, es, etc. (None = sem tradução)"
    )
    engine: Optional[WhisperEngine] = Field(
        default=WhisperEngine.FASTER_WHISPER,
        description="Engine de transcrição: faster-whisper (padrão, 4x mais rápido), openai-whisper, whisperx"
    )


class Job(BaseModel):
    id: str
    input_file: str
    output_file: Optional[str] = None
    status: JobStatus
    operation: str
    language_in: str = "auto"  # Idioma de entrada/origem
    language_out: Optional[str] = None  # Idioma de saída/tradução (None = mesmo que language_in)
    language_detected: Optional[str] = None  # Idioma detectado pelo Whisper (quando language_in="auto")
    engine: WhisperEngine = WhisperEngine.FASTER_WHISPER  # Engine de transcrição usado
    filename: Optional[str] = None
    file_size_input: Optional[int] = None
    file_size_output: Optional[int] = None
    received_at: datetime  # Quando foi recebido
    created_at: datetime   # Alias para received_at (compatibilidade)
    started_at: Optional[datetime] = None     # Quando começou a processar
    completed_at: Optional[datetime] = None   # Quando finalizou
    error_message: Optional[str] = None
    expires_at: datetime
    progress: float = 0.0  # Progresso de 0.0 a 100.0
    transcription_text: Optional[str] = None  # Texto da transcrição
    transcription_segments: Optional[List[TranscriptionSegment]] = None  # Segmentos com timestamps
    
    # Campos de resiliência
    retry_count: int = 0  # Número de tentativas
    status_message: Optional[str] = None  # Mensagem de status atual
    processing_time: Optional[float] = None  # Tempo de processamento em segundos
    dlq_at: Optional[datetime] = None  # Quando foi enviado para DLQ
    result: Optional[Dict] = None  # Resultado completo (TranscriptionResponse serializado)
    
    # Propriedade de compatibilidade com código antigo
    @property
    def language(self) -> str:
        """Compatibilidade: retorna language_in"""
        return self.language_in
    
    @language.setter
    def language(self, value: str):
        """Compatibilidade: define language_in"""
        self.language_in = value
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at
    
    @property
    def needs_translation(self) -> bool:
        """Verifica se precisa traduzir (language_out diferente de language_in/detectado)"""
        return self.language_out is not None and self.language_out != self.language_in
    
    @classmethod
    def create_new(
        cls, 
        filename: str, 
        operation: str = "transcribe", 
        language_in: str = "auto",
        language_out: Optional[str] = None,
        engine: WhisperEngine = WhisperEngine.FASTER_WHISPER
    ) -> "Job":
        # Calcula hash do nome do arquivo + operação + idiomas + engine para criar ID único
        hash_input = f"{filename}_{operation}_{language_in}_{language_out or 'none'}_{engine}"
        job_id = "{}_{}_{}".format(
            hashlib.md5(hash_input.encode()).hexdigest()[:12], 
            operation, 
            language_out or language_in
        )
        
        now = datetime.now()
        cache_ttl_hours = 24
        
        return cls(
            id=job_id,
            input_file="",  # será preenchido depois
            status=JobStatus.QUEUED,
            operation=operation,
            language_in=language_in,
            language_out=language_out,
            engine=engine,
            filename=filename,
            received_at=now,
            created_at=now,
            expires_at=now + timedelta(hours=cache_ttl_hours)
        )