from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class FlexibleSchema(BaseModel):
    """Schema base que preserva compatibilidade com campos extras existentes."""

    model_config = ConfigDict(extra="allow")


class TextResponse(FlexibleSchema):
    text: str = Field(..., description="Texto bruto da transcrição retornado para leitura rápida.")


class DeleteJobResponse(FlexibleSchema):
    message: str = Field(..., description="Resumo da remoção executada.")
    job_id: str = Field(..., description="ID do job removido.")
    files_deleted: int = Field(..., ge=0, description="Quantidade de arquivos excluídos em disco.")


class OrphanedJobInfo(FlexibleSchema):
    job_id: str
    status: str
    created_at: str
    updated_at: str
    age_minutes: float
    filename: Optional[str] = None


class OrphanedJobsResponse(FlexibleSchema):
    status: str
    count: int
    max_age_minutes: int
    orphaned_jobs: list[OrphanedJobInfo] = Field(default_factory=list)


class OrphanCleanupAction(FlexibleSchema):
    job_id: str
    action: str
    age_minutes: float
    files_deleted: list[dict[str, Any]] = Field(default_factory=list)
    reason: Optional[str] = None
    errors: Optional[list[str]] = None


class OrphanCleanupResponse(FlexibleSchema):
    status: str
    message: str
    count: int
    mode: str
    max_age_minutes: int
    space_freed_mb: float
    actions: list[OrphanCleanupAction] = Field(default_factory=list)


class HealthResponse(FlexibleSchema):
    status: str = Field(..., description="Status geral do serviço.", examples=["healthy", "unhealthy"])
    service: str = Field(..., description="Nome técnico do serviço.", examples=["audio-transcription"])
    version: str = Field(..., description="Versão atual da API.")
    timestamp: str = Field(..., description="Timestamp ISO-8601 da verificação.")
    checks: dict[str, Any] = Field(default_factory=dict)


class DetailedHealthResponse(FlexibleSchema):
    overall_healthy: bool = Field(..., description="Indica se todas as checagens críticas passaram.")
    service: Optional[str] = None
    version: Optional[str] = None
    timestamp: Optional[str] = None


class LanguagesResponse(FlexibleSchema):
    transcription: dict[str, Any]
    translation: dict[str, Any]
    models: list[str] = Field(default_factory=list)
    usage_examples: dict[str, Any] = Field(default_factory=dict)


class EnginesResponse(FlexibleSchema):
    engines: list[dict[str, Any]] = Field(default_factory=list)
    default_engine: str
    total_available: int
    recommendation: dict[str, Any] = Field(default_factory=dict)


class AdminCleanupResponse(FlexibleSchema):
    jobs_removed: int = Field(default=0, ge=0, description="Quantidade de jobs removidos durante a limpeza.")
    files_deleted: int = Field(default=0, ge=0, description="Quantidade de arquivos removidos em disco.")
    space_freed_mb: float = Field(default=0.0, ge=0.0, description="Espaço liberado em megabytes.")
    models_deleted: Optional[int] = Field(default=None, ge=0, description="Quantidade de arquivos de modelo removidos na limpeza profunda.")
    redis_flushed: Optional[bool] = Field(default=None, description="Indica se foi executado FLUSHDB no Redis.")
    celery_queue_purged: Optional[bool] = Field(default=None, description="Indica se a fila do Celery foi purgada.")
    celery_tasks_purged: Optional[int] = Field(default=None, ge=0, description="Quantidade de tasks removidas da fila do Celery.")
    errors: list[str] = Field(default_factory=list)
    message: Optional[str] = Field(default=None, description="Resumo textual da limpeza executada.")
    error: Optional[str] = Field(default=None, description="Erro crítico geral, quando a limpeza falha integralmente.")


class AdminStatsResponse(FlexibleSchema):
    total_jobs: int = Field(default=0, ge=0, description="Total de jobs conhecidos pelo serviço.")
    by_status: dict[str, int] = Field(default_factory=dict)
    cache: Optional[dict[str, Any]] = Field(default=None, description="Métricas de arquivos em cache e artefatos persistidos.")


class QueueInfoResponse(FlexibleSchema):
    status: str = Field(..., description="Resultado resumido da consulta da fila.", examples=["success"])
    queue: dict[str, Any] = Field(default_factory=dict, description="Informações atuais da fila e dos workers Celery.")


class AdminOrphanCleanupResponse(FlexibleSchema):
    success: bool = Field(..., description="Indica se a limpeza de órfãos foi concluída com sucesso.")
    stats: Optional[dict[str, Any]] = Field(default=None, description="Estatísticas detalhadas da limpeza executada.")
    error: Optional[str] = Field(default=None, description="Mensagem de erro retornada em caso de falha.")
    timestamp: Optional[str] = Field(default=None, description="Timestamp ISO-8601 da operação.")


class ModelActionResponse(FlexibleSchema):
    success: bool
    message: str


class ModelStatusResponse(FlexibleSchema):
    loaded: bool
    model_name: Optional[str] = None
    device: Optional[str] = None
    memory: dict[str, Any] = Field(default_factory=dict)


class RootResponse(FlexibleSchema):
    service: str = Field(..., description="Nome amigável do serviço.")
    version: str = Field(..., description="Versão atual da API.")
    status: str = Field(..., description="Estado resumido do serviço.", examples=["running"])
    description: str = Field(..., description="Resumo do propósito do serviço.")
    endpoints: dict[str, Any] = Field(
        default_factory=dict,
        description="Catálogo resumido dos principais endpoints públicos do serviço.",
    )
