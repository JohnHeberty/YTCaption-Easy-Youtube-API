from enum import Enum
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import hashlib
import json

from modules.config import get_orchestrator_settings

# Configuração da aplicação
settings = get_orchestrator_settings()

class TranscriptionSegment(BaseModel):
    """Segmento de transcrição com timestamps"""
    text: str
    start: float
    end: float
    duration: float


class PipelineStatus(str, Enum):
    """Status do pipeline completo"""
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    NORMALIZING = "normalizing"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(str, Enum):
    """Status de cada estágio"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStage(BaseModel):
    """Informações de um estágio do pipeline"""
    name: str
    status: StageStatus = StageStatus.PENDING
    job_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    output_file: Optional[str] = None
    progress: float = 0.0
    
    def start(self):
        """Marca estágio como iniciado"""
        self.status = StageStatus.PROCESSING
        self.started_at = datetime.now()
    
    def complete(self, output_file: Optional[str] = None):
        """Marca estágio como completo"""
        self.status = StageStatus.COMPLETED
        self.completed_at = datetime.now()
        self.progress = 100.0
        if output_file:
            self.output_file = output_file
    
    def fail(self, error: str):
        """Marca estágio como falho"""
        self.status = StageStatus.FAILED
        self.completed_at = datetime.now()
        self.error_message = error


class PipelineJob(BaseModel):
    """Job completo do pipeline"""
    id: str
    youtube_url: str
    status: PipelineStatus = PipelineStatus.QUEUED
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # Parâmetros de configuração
    language: str = "auto"
    language_out: Optional[str] = None  # Para tradução
    remove_noise: bool = True
    convert_to_mono: bool = True
    apply_highpass_filter: bool = False
    set_sample_rate_16k: bool = True
    isolate_vocals: bool = False  # Isolamento de vocais (operação pesada)
    
    # Estágios do pipeline
    download_stage: PipelineStage = Field(default_factory=lambda: PipelineStage(name="download"))
    normalization_stage: PipelineStage = Field(default_factory=lambda: PipelineStage(name="normalization"))
    transcription_stage: PipelineStage = Field(default_factory=lambda: PipelineStage(name="transcription"))
    
    # Resultado final
    transcription_text: Optional[str] = None
    transcription_segments: Optional[List[Union[TranscriptionSegment, Dict[str, Any]]]] = None
    transcription_file: Optional[str] = None
    audio_file: Optional[str] = None
    error_message: Optional[str] = None
    
    # Progresso geral
    overall_progress: float = 0.0
    
    @field_validator('transcription_segments', mode='before')
    @classmethod
    def convert_segments(cls, v):
        """Converte dicts em TranscriptionSegment se necessário"""
        if v is None:
            return None
        
        result = []
        for item in v:
            if isinstance(item, dict):
                # Converte dict para TranscriptionSegment
                result.append(TranscriptionSegment(**item))
            elif isinstance(item, TranscriptionSegment):
                # Já é TranscriptionSegment
                result.append(item)
            else:
                # Tipo inesperado, tenta converter
                result.append(item)
        
        return result
    
    @classmethod
    def create_new(cls, youtube_url: str, **kwargs):
        """Cria novo job do pipeline"""
        # Gera ID único baseado na URL e timestamp
        unique_str = f"{youtube_url}_{datetime.now().isoformat()}"
        job_id = hashlib.sha256(unique_str.encode()).hexdigest()[:16]
        
        return cls(
            id=job_id,
            youtube_url=youtube_url,
            **kwargs
        )
    
    def update_progress(self):
        """Atualiza progresso geral baseado nos estágios"""
        stages = [self.download_stage, self.normalization_stage, self.transcription_stage]
        completed_stages = sum(1 for s in stages if s.status == StageStatus.COMPLETED)
        processing_stage = next((s for s in stages if s.status == StageStatus.PROCESSING), None)
        
        # Cada estágio vale 33.3%
        base_progress = (completed_stages / 3) * 100
        
        # Adiciona progresso do estágio atual
        if processing_stage:
            stage_progress = (processing_stage.progress / 3)
            base_progress += stage_progress
        
        self.overall_progress = min(100.0, base_progress)
        self.updated_at = datetime.now()
    
    def get_current_stage(self) -> Optional[PipelineStage]:
        """Retorna estágio atual em processamento"""
        stages = [self.download_stage, self.normalization_stage, self.transcription_stage]
        return next((s for s in stages if s.status == StageStatus.PROCESSING), None)
    
    def mark_as_completed(self):
        """Marca job como completo"""
        self.status = PipelineStatus.COMPLETED
        self.completed_at = datetime.now()
        self.overall_progress = 100.0
        self.updated_at = datetime.now()
    
    def mark_as_failed(self, error: str):
        """Marca job como falho"""
        self.status = PipelineStatus.FAILED
        self.completed_at = datetime.now()
        self.error_message = error
        self.updated_at = datetime.now()


class PipelineRequest(BaseModel):
    """Request para iniciar pipeline"""
    youtube_url: str = Field("https://www.youtube.com/watch?v=_xhulIrM6hw", description="URL do vídeo do YouTube")
    language: Optional[str] = Field(settings["default_language"], description="Idioma para transcrição (ISO 639-1) ou 'auto'")
    language_out: Optional[str] = Field(settings["default_language"], description="Idioma de saída para tradução (ISO 639-1)")
    remove_noise: Optional[bool] = Field(settings["default_remove_noise"], description="Remover ruído de fundo")
    convert_to_mono: Optional[bool] = Field(settings["default_convert_mono"], description="Converter para mono")
    apply_highpass_filter: Optional[bool] = Field(settings["default_highpass_filter"], description="Aplicar filtro high-pass")
    set_sample_rate_16k: Optional[bool] = Field(settings["default_sample_rate_16k"], description="Sample rate 16kHz")

class PipelineResponse(BaseModel):
    """Resposta da criação do pipeline"""
    job_id: str
    status: PipelineStatus
    message: str
    youtube_url: str
    overall_progress: float = 0.0


class PipelineStatusResponse(BaseModel):
    """Resposta detalhada do status do pipeline"""
    job_id: str
    youtube_url: str
    status: PipelineStatus
    overall_progress: float
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    
    # Status dos estágios
    stages: Dict[str, Dict[str, Any]]
    
    # Resultado
    transcription_text: Optional[str]
    transcription_segments: Optional[List[Dict[str, Any]]]
    transcription_file: Optional[str]
    audio_file: Optional[str]
    error_message: Optional[str]


class HealthResponse(BaseModel):
    """Resposta do health check"""
    status: str
    service: str
    version: str
    timestamp: datetime
    microservices: Dict[str, str]  # nome -> status
    uptime_seconds: Optional[float] = None
    redis_connected: bool = False
