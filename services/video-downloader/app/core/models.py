"""
Video Downloader job model extending the standard common job.

Adds service-specific fields (url, quality, filename, etc.) while
inheriting the standard lifecycle methods and stage tracking from
StandardJob.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator

from common.job_utils.models import StandardJob, JobStatus, StageInfo
from app.core.constants import DEFAULT_QUALITY, QUALITY_FORMATS


class VideoQuality(str, Enum):
    BEST = "best"
    WORST = "worst"
    Q720P = "720p"
    Q480P = "480p"
    Q360P = "360p"
    AUDIO = "audio"


class VideoDownloadJob(StandardJob):
    """Job completo do pipeline de download.

    Campos de entrada da pipeline:
    - `url`
    - `quality`

    Campos internos/operacionais:
    - `filename`, `file_path`, `file_size`, `current_user_agent`
    - status/timestamps/erro herdados de `StandardJob`
    """

    id: str = Field(default="", description="ID determinístico do job (prefixo `vd_`).")
    status: JobStatus = Field(
        default=JobStatus.PENDING,
        description="Estado do job na pipeline (`queued`, `processing`, `completed`, `failed`).",
    )
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="Progresso do processamento em percentual.")
    progress_message: Optional[str] = Field(
        default=None,
        description="Mensagem de progresso para acompanhamento do estágio atual.",
    )
    created_at: datetime = Field(..., description="Data/hora de criação do job.")
    started_at: Optional[datetime] = Field(default=None, description="Data/hora de início do processamento.")
    completed_at: Optional[datetime] = Field(default=None, description="Data/hora de conclusão do processamento.")
    expires_at: datetime = Field(..., description="Data/hora de expiração do job e artefatos em cache.")
    error_message: Optional[str] = Field(default=None, description="Mensagem de erro quando o job falha.")
    error_type: Optional[str] = Field(default=None, description="Tipo técnico do erro para troubleshooting.")
    correlation_id: Optional[str] = Field(default=None, description="ID opcional de correlação entre serviços da pipeline.")
    retry_count: int = Field(default=0, description="Quantidade de tentativas/retries do job.")
    stages: dict[str, StageInfo] = Field(
        default_factory=dict,
        description="Mapa de estágios internos da pipeline e seus respectivos status/progresso.",
    )
    url: str = Field(default="", description="URL do vídeo no YouTube a ser baixado.")
    quality: str = Field(
        default=DEFAULT_QUALITY,
        description="Preset de qualidade (`best`, `worst`, `720p`, `480p`, `360p`, `audio`).",
    )
    filename: Optional[str] = Field(default=None, description="Nome final do arquivo baixado (preenchido após processamento).")
    file_path: Optional[str] = Field(default=None, description="Caminho local do arquivo no cache/downloads (campo interno).")
    file_size: Optional[int] = Field(default=None, description="Tamanho do arquivo em bytes (preenchido ao concluir download).")
    current_user_agent: Optional[str] = Field(
        default=None,
        description="User-Agent em uso na tentativa atual (campo interno operacional).",
    )
    
    # Backward compatibility attribute for legacy code that uses received_at
    @property
    def received_at(self) -> datetime:
        return self.created_at

    class Config:
        json_encoders = {**StandardJob.Config.json_encoders}

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, value: str) -> str:
        normalized = (value or DEFAULT_QUALITY).lower()
        if normalized not in QUALITY_FORMATS:
            allowed = ", ".join(sorted(QUALITY_FORMATS.keys()))
            raise ValueError(f"Invalid quality '{value}'. Allowed values: {allowed}")
        return normalized

    @classmethod
    def create_new(cls, url: str, quality: str = DEFAULT_QUALITY) -> "VideoDownloadJob":
        import re
        video_id = None
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                break

        if not video_id:
            if len(url) == 11 and url.replace('-', '').replace('_', '').isalnum():
                video_id = url
                url = f"https://www.youtube.com/watch?v={video_id}"

        from common.job_utils.models import generate_job_id
        job_id = generate_job_id(video_id or url, quality, prefix="vd_")

        job = cls(
            id=job_id,
            url=url,
            quality=quality,
        )
        job.mark_as_queued()
        return job


class VideoDownloadJobRequest(BaseModel):
    """Payload de entrada para POST /jobs.

    Mantido intencionalmente mínimo para evitar confusão na API:
    - obrigatório: `url`
    - opcional: `quality`
    """

    url: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="URL completa do vídeo no YouTube.",
        examples=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
    )
    quality: str = Field(
        default=DEFAULT_QUALITY,
        description="Qualidade desejada (`best`, `worst`, `720p`, `480p`, `360p`, `audio`).",
        examples=["best", "720p", "audio"],
        json_schema_extra={"enum": ["best", "worst", "720p", "480p", "360p", "audio"]},
    )

    @field_validator("quality")
    @classmethod
    def validate_request_quality(cls, value: str) -> str:
        normalized = (value or DEFAULT_QUALITY).lower()
        if normalized not in QUALITY_FORMATS:
            allowed = ", ".join(sorted(QUALITY_FORMATS.keys()))
            raise ValueError(f"Invalid quality '{value}'. Allowed values: {allowed}")
        return normalized

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "quality": "720p",
            }
        }


class VideoDownloadJobCreatedResponse(BaseModel):
    """Response enxuto para criação de job (POST /jobs).

    Exibe somente campos úteis para o cliente iniciar o polling.
    Campos internos do pipeline permanecem no endpoint de status.
    """

    id: str = Field(..., description="ID do job criado para consultar status/download.")
    status: JobStatus = Field(..., description="Status inicial do job, normalmente `queued` ou `processing`.")
    url: str = Field(..., description="URL alvo do download.")
    quality: str = Field(..., description="Qualidade aplicada no job.")
    progress: float = Field(..., ge=0.0, le=100.0, description="Progresso inicial do job.")
    created_at: datetime = Field(..., description="Data/hora de criação do job.")
    expires_at: datetime = Field(..., description="Data/hora de expiração do job no cache.")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "vd_abcdef1234567890",
                "status": "queued",
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "quality": "720p",
                "progress": 0.0,
                "created_at": "2026-04-30T10:00:00-03:00",
                "expires_at": "2026-05-01T10:00:00-03:00",
            }
        }

    @classmethod
    def from_job(cls, job: VideoDownloadJob) -> "VideoDownloadJobCreatedResponse":
        return cls(
            id=job.id,
            status=job.status,
            url=job.url,
            quality=job.quality,
            progress=job.progress,
            created_at=job.created_at,
            expires_at=job.expires_at,
        )


class LegacyJobAdapter:
    """Adapts between the old Job model and the new VideoDownloadJob.

    Provides backward compatibility for code that references the old
    Job model fields (received_at, updated_at, job_id, error, etc.).
    """

    @staticmethod
    def to_response(job: VideoDownloadJob) -> dict:
        return job.model_dump(mode="json")


# Backward compatibility aliases
Job = VideoDownloadJob
JobRequest = VideoDownloadJobRequest


class DeleteJobResponse(BaseModel):
    message: str = Field(..., description="Resultado da remoção do job.")
    job_id: str = Field(..., description="ID do job removido.")
    files_deleted: int = Field(..., ge=0, description="Quantidade de arquivos removidos em disco.")


class OrphanedJobInfo(BaseModel):
    job_id: str = Field(..., description="ID do job órfão detectado.")
    status: str = Field(..., description="Status atual do job órfão.")
    created_at: str = Field(..., description="Timestamp de criação do job (ISO 8601).")
    started_at: Optional[str] = Field(default=None, description="Timestamp de início, quando disponível.")
    age_minutes: float = Field(..., ge=0.0, description="Tempo desde o início do job em minutos.")
    url: str = Field(..., description="URL de origem do download.")


class OrphanedJobsResponse(BaseModel):
    status: str = Field(..., description="Status da operação.", examples=["success"])
    count: int = Field(..., ge=0, description="Quantidade de jobs órfãos encontrados.")
    max_age_minutes: int = Field(..., ge=1, description="Janela de idade usada na consulta.")
    orphaned_jobs: List[OrphanedJobInfo] = Field(
        default_factory=list,
        description="Lista de jobs órfãos detectados.",
    )


class OrphanedCleanupAction(BaseModel):
    job_id: str = Field(..., description="ID do job processado na limpeza.")
    action: str = Field(..., description="Ação executada: marked_as_failed ou deleted.")
    age_minutes: float = Field(..., ge=0.0, description="Idade do job em minutos no momento da ação.")


class OrphanedCleanupResponse(BaseModel):
    status: str = Field(..., description="Status da operação.", examples=["success"])
    message: str = Field(..., description="Resumo da limpeza executada.")
    count: int = Field(..., ge=0, description="Quantidade de jobs tratados.")
    mode: Optional[str] = Field(default=None, description="Modo aplicado: mark_as_failed ou delete.")
    actions: List[OrphanedCleanupAction] = Field(default_factory=list, description="Ações executadas por job.")


class QueueInfoResponse(BaseModel):
    status: str = Field(..., description="Status da consulta da fila.", examples=["success"])
    queue: Dict[str, Any] = Field(default_factory=dict, description="Informações atuais da fila do Celery.")


class StatsResponse(BaseModel):
    total_jobs: int = Field(default=0, ge=0, description="Total de jobs conhecidos.")
    by_status: Dict[str, int] = Field(default_factory=dict, description="Contagem de jobs por status.")
    cache: Dict[str, Any] = Field(default_factory=dict, description="Métricas de cache local.")
    celery: Dict[str, Any] = Field(default_factory=dict, description="Métricas/estado do Celery.")


class CleanupResponse(BaseModel):
    jobs_removed: int = Field(default=0, ge=0, description="Quantidade de jobs removidos.")
    files_deleted: int = Field(default=0, ge=0, description="Quantidade de arquivos removidos.")
    space_freed_mb: float = Field(default=0.0, ge=0.0, description="Espaço liberado em MB.")
    errors: List[str] = Field(default_factory=list, description="Lista de erros da limpeza.")
    redis_flushed: Optional[bool] = Field(default=None, description="Indica se houve flush completo no Redis.")
    celery_queue_purged: Optional[bool] = Field(default=None, description="Indica se a fila do Celery foi limpa.")
    celery_tasks_purged: Optional[int] = Field(default=None, ge=0, description="Quantidade de tasks removidas da fila Celery.")
    message: Optional[str] = Field(default=None, description="Resumo textual da operação de cleanup.")
    error: Optional[str] = Field(default=None, description="Erro crítico geral, quando houver.")


class FixStuckJobsResponse(BaseModel):
    fixed_count: int = Field(..., ge=0, description="Quantidade de jobs travados corrigidos.")
    max_age_minutes: int = Field(..., ge=1, description="Idade mínima usada para considerar job travado.")
    message: str = Field(..., description="Resumo da operação.")


class RootEndpointCatalog(BaseModel):
    health: str = Field(..., description="Endpoint principal de health check.")
    docs: str = Field(..., description="Endpoint da interface Swagger/OpenAPI.")
    jobs: Dict[str, str] = Field(default_factory=dict, description="Operações principais relacionadas a jobs de download.")
    admin: Dict[str, str] = Field(default_factory=dict, description="Operações administrativas do serviço.")
    user_agents: Dict[str, str] = Field(default_factory=dict, description="Operações de inspeção e reset de User-Agents.")


class RootResponse(BaseModel):
    service: str = Field(..., description="Nome amigável do serviço.")
    version: str = Field(..., description="Versão atual da API.")
    status: str = Field(..., description="Estado resumido do serviço.", examples=["running"])
    description: str = Field(..., description="Resumo do propósito do serviço.")
    endpoints: RootEndpointCatalog = Field(..., description="Catálogo resumido das rotas públicas do serviço.")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Status geral do serviço.", examples=["healthy", "degraded", "unhealthy"])
    service: str = Field(..., description="Nome técnico do serviço.", examples=["video-downloader"])
    timestamp: str = Field(..., description="Timestamp ISO-8601 da verificação.")
    checks: Dict[str, str] = Field(default_factory=dict, description="Resumo das checagens principais do serviço.")
    active_workers: Optional[int] = Field(default=None, ge=0, description="Quantidade de workers Celery ativos detectados.")
    warning: Optional[str] = Field(default=None, description="Mensagem adicional quando o serviço estiver degradado.")


class UserAgentStatsResponse(BaseModel):
    total_user_agents: int = Field(..., ge=0, description="Quantidade total de User-Agents cadastrados.")
    quarantined_count: int = Field(..., ge=0, description="Quantidade de User-Agents atualmente em quarentena.")
    available_count: int = Field(..., ge=0, description="Quantidade de User-Agents disponíveis para uso.")
    error_cache_size: int = Field(..., ge=0, description="Quantidade de entradas no cache de erro dos User-Agents.")
    quarantine_hours: int = Field(..., ge=0, description="Tempo de quarentena configurado, em horas.")
    max_error_count: int = Field(..., ge=0, description="Limite de erros antes de um User-Agent entrar em quarentena.")
    average_quality: float = Field(..., ge=0.0, le=1.0, description="Média do score de qualidade dos User-Agents amostrados.")
    quarantined_uas: List[str] = Field(default_factory=list, description="Amostra reduzida dos User-Agents em quarentena.")


class UserAgentResetResponse(BaseModel):
    success: bool = Field(..., description="Indica se o reset foi executado com sucesso.")
    user_agent: str = Field(..., description="User-Agent efetivamente resetado ou o identificador informado.")
    message: str = Field(..., description="Resumo textual do resultado do reset.")