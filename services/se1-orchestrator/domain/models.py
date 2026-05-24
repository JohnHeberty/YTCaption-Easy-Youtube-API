"""
Modelos de domínio do orquestrador.

Modelos Pydantic para representação de jobs e estágios do pipeline.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo

    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")

    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

from pydantic import BaseModel, Field, field_validator
import hashlib


class TranscriptionSegment(BaseModel):
    """Segmento de transcrição com timestamps."""

    text: str
    start: float
    end: float
    duration: float


class PipelineStatus(str, Enum):
    """Status do pipeline completo."""

    QUEUED = "queued"
    DOWNLOADING = "downloading"
    NORMALIZING = "normalizing"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(str, Enum):
    """Status de cada estágio."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStage(BaseModel):
    """Informações de um estágio do pipeline."""

    name: str
    status: StageStatus = StageStatus.PENDING
    job_id: Optional[str] = None
    received_at: datetime = Field(default_factory=now_brazil)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    output_file: Optional[str] = None
    progress: float = 0.0

    def start(self) -> None:
        """Marca estágio como iniciado."""
        self.status = StageStatus.PROCESSING
        if not self.started_at:
            self.started_at = now_brazil()

    def complete(self, output_file: Optional[str] = None) -> None:
        """Marca estágio como completo."""
        self.status = StageStatus.COMPLETED
        self.completed_at = now_brazil()
        self.progress = 100.0
        if output_file:
            self.output_file = output_file

    def fail(self, error: str) -> None:
        """Marca estágio como falho."""
        self.status = StageStatus.FAILED
        self.completed_at = now_brazil()
        self.error_message = error


class PipelineJob(BaseModel):
    """Job completo do pipeline."""

    id: str
    youtube_url: str
    status: PipelineStatus = PipelineStatus.QUEUED
    received_at: datetime = Field(default_factory=now_brazil)
    created_at: datetime = Field(default_factory=now_brazil)
    started_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=now_brazil)
    completed_at: Optional[datetime] = None

    # Parâmetros de configuração
    language: str = "auto"
    language_out: Optional[str] = None
    remove_noise: bool = True
    convert_to_mono: bool = True
    apply_highpass_filter: bool = False
    set_sample_rate_16k: bool = True
    isolate_vocals: bool = False

    # Estágios do pipeline
    download_stage: PipelineStage = Field(
        default_factory=lambda: PipelineStage(name="download")
    )
    normalization_stage: PipelineStage = Field(
        default_factory=lambda: PipelineStage(name="normalization")
    )
    transcription_stage: PipelineStage = Field(
        default_factory=lambda: PipelineStage(name="transcription")
    )

    # Resultado final
    transcription_text: Optional[str] = None
    transcription_segments: Optional[List[Union[TranscriptionSegment, Dict[str, Any]]]] = None
    transcription_file: Optional[str] = None
    audio_file: Optional[str] = None
    error_message: Optional[str] = None

    # Progresso geral
    overall_progress: float = 0.0

    @field_validator("transcription_segments", mode="before")
    @classmethod
    def convert_segments(cls, v: Any) -> Optional[List[TranscriptionSegment]]:
        """Converte dicts em TranscriptionSegment se necessário."""
        if v is None:
            return None

        result: List[TranscriptionSegment] = []
        for item in v:
            if isinstance(item, dict):
                result.append(TranscriptionSegment(**item))
            elif isinstance(item, TranscriptionSegment):
                result.append(item)
        return result

    @classmethod
    def create_new(cls, youtube_url: str, **kwargs: Any) -> "PipelineJob":
        """
        Cria novo job do pipeline.

        Args:
            youtube_url: URL do vídeo do YouTube
            **kwargs: Parâmetros adicionais

        Returns:
            PipelineJob: Nova instância do job
        """
        # Gera ID único baseado na URL e timestamp
        unique_str = f"{youtube_url}_{now_brazil().isoformat()}"
        job_id = hashlib.sha256(unique_str.encode()).hexdigest()[:16]

        return cls(id=job_id, youtube_url=youtube_url, **kwargs)

    def update_progress(self) -> None:
        """Atualiza progresso geral baseado nos estágios."""
        stages = [
            self.download_stage,
            self.normalization_stage,
            self.transcription_stage,
        ]
        completed_stages = sum(1 for s in stages if s.status == StageStatus.COMPLETED)
        processing_stage = next(
            (s for s in stages if s.status == StageStatus.PROCESSING), None
        )

        # Cada estágio vale 33.3%
        base_progress = (completed_stages / 3) * 100

        # Adiciona progresso do estágio atual
        if processing_stage:
            stage_progress = processing_stage.progress / 3
            base_progress += stage_progress

        self.overall_progress = min(100.0, base_progress)
        self.updated_at = now_brazil()

    def get_current_stage(self) -> Optional[PipelineStage]:
        """Retorna estágio atual em processamento."""
        stages = [
            self.download_stage,
            self.normalization_stage,
            self.transcription_stage,
        ]
        return next((s for s in stages if s.status == StageStatus.PROCESSING), None)

    def mark_as_completed(self) -> None:
        """Marca job como completo."""
        self.status = PipelineStatus.COMPLETED
        self.completed_at = now_brazil()
        self.overall_progress = 100.0
        self.updated_at = now_brazil()

    def mark_as_failed(self, error: str) -> None:
        """Marca job como falho."""
        self.status = PipelineStatus.FAILED
        self.completed_at = now_brazil()
        self.error_message = error
        self.updated_at = now_brazil()


class PipelineRequest(BaseModel):
    """Request para iniciar pipeline."""

    youtube_url: str = Field(
        default="https://www.youtube.com/watch?v=_xhulIrM6hw",
        description="URL do vídeo do YouTube para iniciar o pipeline completo.",
        examples=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
    )
    language: Optional[str] = Field(default="auto", description="Idioma para transcrição (auto, pt, en, es, ...)", examples=["auto", "pt", "en"])
    language_out: Optional[str] = Field(default=None, description="Idioma de saída para tradução (quando aplicável).", examples=["pt", "en"])
    remove_noise: Optional[bool] = Field(default=True, description="Remover ruído de fundo do áudio.")
    convert_to_mono: Optional[bool] = Field(default=True, description="Converter áudio para canal mono.")
    apply_highpass_filter: Optional[bool] = Field(default=False, description="Aplicar filtro passa-alta no áudio.")
    set_sample_rate_16k: Optional[bool] = Field(default=True, description="Forçar sample rate em 16kHz.")

    class Config:
        json_schema_extra = {
            "example": {
                "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "language": "pt",
                "language_out": "en",
                "remove_noise": True,
                "convert_to_mono": True,
                "apply_highpass_filter": False,
                "set_sample_rate_16k": True,
            }
        }


class PipelineResponse(BaseModel):
    """Resposta da criação do pipeline."""

    job_id: str = Field(..., description="ID do job para acompanhar progresso em /jobs/{job_id}.")
    status: PipelineStatus = Field(..., description="Status inicial do pipeline.")
    message: str = Field(..., description="Mensagem de orientação para acompanhamento do job.")
    youtube_url: str = Field(..., description="URL original recebida no request.")
    overall_progress: float = Field(default=0.0, ge=0.0, le=100.0, description="Progresso geral do pipeline.")


class PipelineStatusResponse(BaseModel):
    """Resposta detalhada do status do pipeline."""

    job_id: str = Field(..., description="ID do job consultado.")
    youtube_url: str = Field(..., description="URL do vídeo associado ao pipeline.")
    status: PipelineStatus = Field(..., description="Status atual do pipeline.")
    overall_progress: float = Field(..., ge=0.0, le=100.0, description="Progresso geral em percentual.")
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    stages: Dict[str, Dict[str, Any]] = Field(..., description="Detalhes de progresso por estágio da pipeline.")
    transcription_text: Optional[str] = None
    transcription_segments: Optional[List[Dict[str, Any]]] = None
    transcription_file: Optional[str] = None
    audio_file: Optional[str] = None
    error_message: Optional[str] = Field(default=None, description="Mensagem de erro, quando o pipeline falha.")


class JobSummary(BaseModel):
    job_id: str = Field(..., description="ID do job.")
    youtube_url: str = Field(..., description="URL do vídeo processado.")
    status: str = Field(..., description="Status textual do job.")
    progress: float = Field(..., ge=0.0, le=100.0, description="Progresso atual do job.")
    created_at: datetime = Field(..., description="Data/hora de criação.")
    updated_at: datetime = Field(..., description="Data/hora da última atualização.")


class JobListResponse(BaseModel):
    total: int = Field(..., ge=0, description="Total de jobs retornados.")
    jobs: List[JobSummary] = Field(default_factory=list, description="Lista resumida de jobs.")


class AdminCleanupResponse(BaseModel):
    message: str = Field(..., description="Resumo da execução do cleanup.")
    jobs_removed: int = Field(default=0, ge=0, description="Quantidade de jobs removidos.")
    logs_cleaned: bool = Field(default=False, description="Indica se os logs foram limpos.")


class OrchestratorStatsInfo(BaseModel):
    version: str = Field(..., description="Versão atual do orchestrator.")
    environment: str = Field(..., description="Ambiente de execução configurado.")


class OrchestratorSettingsSnapshot(BaseModel):
    cache_ttl_hours: int = Field(..., description="TTL de cache dos jobs em horas.")
    job_timeout_minutes: int = Field(..., description="Tempo máximo esperado por job, em minutos.")
    poll_interval_initial: int = Field(..., description="Intervalo inicial de polling entre tentativas.")
    poll_interval_max: int = Field(..., description="Intervalo máximo de polling permitido.")
    max_poll_attempts: int = Field(..., description="Quantidade máxima de tentativas de polling configurada.")


class AdminStatsResponse(BaseModel):
    orchestrator: OrchestratorStatsInfo = Field(..., description="Informações gerais do orchestrator.")
    redis: Dict[str, Any] = Field(default_factory=dict, description="Métricas relacionadas ao Redis.")
    settings: OrchestratorSettingsSnapshot = Field(..., description="Configurações ativas relevantes.")


class FactoryResetOrchestratorResult(BaseModel):
    jobs_removed: int = Field(default=0, ge=0, description="Quantidade de jobs removidos do Redis do orchestrator.")
    redis_flushed: bool = Field(default=False, description="Indica se o Redis do orchestrator foi totalmente limpo.")
    logs_cleaned: bool = Field(default=False, description="Indica se os logs locais do orchestrator foram removidos.")


class FactoryResetServiceResult(BaseModel):
    status: str = Field(..., description="Resultado da chamada de cleanup ao microserviço.")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Payload de sucesso retornado pelo microserviço, quando disponível.")
    error: Optional[str] = Field(default=None, description="Mensagem de erro quando o cleanup remoto falha.")


class FactoryResetResponse(BaseModel):
    message: str = Field(..., description="Resumo da operação de factory reset.")
    orchestrator: FactoryResetOrchestratorResult = Field(..., description="Resultado da limpeza local do orchestrator.")
    microservices: Dict[str, FactoryResetServiceResult] = Field(default_factory=dict, description="Resultado da limpeza por microserviço.")
    warning: str = Field(..., description="Aviso sobre impacto destrutivo do reset.")


class HealthResponse(BaseModel):
    """Resposta do health check."""

    status: str = Field(..., description="Status geral do orchestrator.", examples=["healthy", "degraded", "unhealthy"])
    service: str = Field(..., description="Nome técnico do serviço.", examples=["orchestrator"])
    version: str = Field(..., description="Versão atual da API.")
    timestamp: datetime = Field(..., description="Timestamp da verificação de saúde.")
    microservices: Dict[str, str] = Field(default_factory=dict, description="Status resumido dos microserviços dependentes.")
    uptime_seconds: Optional[float] = Field(default=None, ge=0.0, description="Tempo de atividade do processo em segundos.")
    redis_connected: bool = Field(default=False, description="Indica se a conexão com o Redis foi validada com sucesso.")


class RootResponse(BaseModel):
    service: str = Field(..., description="Nome amigável do serviço.")
    version: str = Field(..., description="Versão atual da API.")
    status: str = Field(..., description="Estado resumido do serviço.", examples=["running"])
    endpoints: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapa resumido dos principais endpoints públicos do orchestrator.",
    )
