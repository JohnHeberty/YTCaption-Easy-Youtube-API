"""
YouTube search job model.

Adds service-specific search fields (search type, query, results)
while inheriting standard lifecycle.
"""
import hashlib
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from common.datetime_utils import now_brazil


class SearchType(str, Enum):
    VIDEO_INFO = "video_info"
    CHANNEL_INFO = "channel_info"
    PLAYLIST_INFO = "playlist_info"
    VIDEO = "video"
    RELATED_VIDEOS = "related_videos"
    SHORTS = "shorts"


class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageInfo(BaseModel):
    name: str
    display_name: str = ""
    status: StageStatus = StageStatus.PENDING
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    progress_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class Job(BaseModel):
    id: str
    status: JobStatus = JobStatus.PENDING
    search_type: SearchType = SearchType.VIDEO
    query: Optional[str] = None
    video_id: Optional[str] = None
    channel_id: Optional[str] = None
    playlist_id: Optional[str] = None
    max_results: int = 10
    result: Optional[Dict[str, Any]] = None
    progress: float = 0.0
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=now_brazil)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    stages: List[StageInfo] = Field(default_factory=list)

    def mark_as_queued(self):
        self.status = JobStatus.QUEUED

    def mark_as_processing(self):
        self.status = JobStatus.PROCESSING
        self.started_at = now_brazil()

    def mark_as_completed(self):
        self.status = JobStatus.COMPLETED
        self.completed_at = now_brazil()
        self.progress = 100.0

    def mark_as_failed(self, error: str):
        self.status = JobStatus.FAILED
        self.error_message = error
        self.completed_at = now_brazil()

    def add_stage(self, name: str, display_name: str = ""):
        stage = StageInfo(name=name, display_name=display_name)
        self.stages.append(stage)
        return stage


def generate_job_id(params: str, prefix: str = "ys_") -> str:
    hash_obj = hashlib.sha256(params.encode())
    return f"{prefix}{hash_obj.hexdigest()[:12]}"


class YouTubeSearchJob(Job):
    @classmethod
    def create_new(cls, search_type: SearchType, **kwargs) -> "YouTubeSearchJob":
        params = f"{search_type.value}_{kwargs.get('query', '')}_{kwargs.get('video_id', '')}_{kwargs.get('channel_id', '')}_{kwargs.get('playlist_id', '')}"
        job_id = generate_job_id(params, prefix="ys_")

        job = cls(
            id=job_id,
            search_type=search_type,
            **kwargs,
        )
        job.add_stage("search", f"Searching {search_type.value}")
        job.mark_as_queued()
        return job


class VideoInfo(BaseModel):
    video_id: str
    title: Optional[str] = None
    thumbnails: Optional[Dict[str, Any]] = None
    url: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[str] = None
    duration_seconds: Optional[int] = None
    views_count: Optional[int] = None
    view_count_text: Optional[str] = None
    likes_count: Optional[int] = None
    publish_date: Optional[int] = None
    publish_date_text: Optional[str] = None
    upload_date: Optional[int] = None


class ChannelInfo(BaseModel):
    channel_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    subscriber_count: Optional[int] = None
    video_count: Optional[int] = None
    playlist_uploads_id: Optional[str] = None


class PlaylistInfo(BaseModel):
    playlist_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    video_count: Optional[int] = None
    channel_id: Optional[str] = None


class SearchRequest(BaseModel):
    search_type: SearchType
    query: Optional[str] = None
    video_id: Optional[str] = None
    channel_id: Optional[str] = None
    playlist_id: Optional[str] = None
    max_results: int = 10


class JobListResponse(BaseModel):
    jobs: List[Job]
    total: int


class DeleteJobResponse(BaseModel):
    message: str = Field(..., description="Resultado da remoção do job.")
    job_id: str = Field(..., description="ID do job removido.")


class SearchStatsSummary(BaseModel):
    total_jobs: int = Field(..., description="Quantidade total de jobs armazenados no Redis.")
    by_status: Dict[str, int] = Field(
        default_factory=dict,
        description="Quantidade de jobs agrupada por status.",
        examples=[{"completed": 12, "processing": 1, "failed": 2}],
    )


class HealthCheckComponent(BaseModel):
    status: str = Field(..., description="Status do componente verificado.")
    message: Optional[str] = Field(
        default=None,
        description="Mensagem adicional da verificação quando aplicável.",
    )
    jobs: Optional[SearchStatsSummary] = Field(
        default=None,
        description="Resumo de jobs quando a checagem do Redis estiver disponível.",
    )
    free_gb: Optional[float] = Field(
        default=None,
        description="Espaço livre em disco, em gigabytes.",
    )
    percent_free: Optional[float] = Field(
        default=None,
        description="Percentual de espaço livre em disco.",
    )
    workers: Optional[int] = Field(
        default=None,
        description="Quantidade de workers Celery ativos detectados.",
    )
    active_tasks: Optional[int] = Field(
        default=None,
        description="Quantidade total de tasks ativas nos workers Celery.",
    )


class HealthResponse(BaseModel):
    status: str = Field(..., description="Status geral do serviço.", examples=["healthy"])
    service: str = Field(..., description="Nome do serviço.", examples=["youtube-search"])
    version: str = Field(..., description="Versão atual do serviço.")
    timestamp: str = Field(..., description="Timestamp ISO-8601 da verificação.")
    checks: Dict[str, HealthCheckComponent] = Field(
        default_factory=dict,
        description="Resultado detalhado das verificações de dependências e recursos.",
    )


class RootResponse(BaseModel):
    service: str = Field(..., description="Nome amigável do serviço.")
    version: str = Field(..., description="Versão atual do serviço.")
    status: str = Field(..., description="Estado resumido do serviço.", examples=["running"])
    endpoints: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapa com os principais endpoints públicos e seu uso resumido.",
    )


class CleanupResponse(BaseModel):
    jobs_removed: int = Field(..., description="Quantidade de jobs removidos durante a limpeza.")
    message: str = Field(..., description="Resumo legível do resultado da limpeza.")
    redis_flushed: bool = Field(
        default=False,
        description="Indica se um FLUSHDB foi executado no Redis.",
    )
    celery_queue_purged: bool = Field(
        default=False,
        description="Indica se a fila do Celery foi esvaziada.",
    )
    celery_tasks_purged: int = Field(
        default=0,
        description="Quantidade de tasks removidas da fila do Celery.",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Lista de erros não fatais encontrados durante a limpeza.",
    )


class CeleryStatsResponse(BaseModel):
    active_workers: int = Field(..., description="Quantidade de workers Celery ativos.")
    active_tasks: int = Field(..., description="Quantidade total de tasks ativas.")
    broker: str = Field(..., description="Broker configurado para o Celery.")
    backend: str = Field(..., description="Backend configurado para o Celery.")
    queue: str = Field(..., description="Nome da fila principal do serviço.")
    error: Optional[str] = Field(
        default=None,
        description="Mensagem de erro quando não foi possível consultar o Celery.",
    )
    status: Optional[str] = Field(
        default=None,
        description="Estado resumido da integração com o Celery quando indisponível.",
    )


class SearchServiceStatsResponse(SearchStatsSummary):
    celery: CeleryStatsResponse = Field(
        ...,
        description="Resumo operacional do Celery para este serviço.",
    )


class QueueStatsResponse(BaseModel):
    broker: Optional[str] = Field(
        default=None,
        description="Broker configurado para processar a fila.",
    )
    queue_name: Optional[str] = Field(
        default=None,
        description="Nome da fila monitorada.",
    )
    active_workers: int = Field(
        default=0,
        description="Quantidade de workers ativos no momento da consulta.",
    )
    registered_tasks: List[str] = Field(
        default_factory=list,
        description="Tasks registradas nos workers Celery.",
    )
    active_tasks: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Tasks ativas por worker.",
    )
    scheduled_tasks: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Tasks agendadas por worker.",
    )
    is_running: bool = Field(
        ...,
        description="Indica se foi possível detectar workers ativos ou responder à inspeção.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Mensagem de erro retornada quando a inspeção da fila falha.",
    )