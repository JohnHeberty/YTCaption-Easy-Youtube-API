"""
Audio normalization job model extending StandardJob.

Adds service-specific fields (audio processing parameters, file paths)
while inheriting standard lifecycle methods from common.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import hashlib

from common.job_utils.models import StandardJob, JobStatus
from common.datetime_utils import now_brazil


class AudioNormJob(StandardJob):
    input_file: Optional[str] = Field(
        default=None,
        description="Caminho interno do arquivo de entrada salvo no servidor.",
    )
    output_file: Optional[str] = Field(
        default=None,
        description="Caminho interno do arquivo final processado.",
    )
    filename: Optional[str] = Field(
        default=None,
        description="Nome original do arquivo enviado.",
        examples=["podcast_ep01.mp3"],
    )
    file_size_input: Optional[int] = Field(
        default=None,
        ge=0,
        description="Tamanho do arquivo de entrada em bytes.",
    )
    file_size_output: Optional[int] = Field(
        default=None,
        ge=0,
        description="Tamanho do arquivo processado em bytes.",
    )

    # Processing parameters
    remove_noise: bool = Field(
        default=True,
        description="Ativa redução de ruído de fundo.",
    )
    convert_to_mono: bool = Field(
        default=True,
        description="Converte o áudio para canal mono.",
    )
    apply_highpass_filter: bool = Field(
        default=False,
        description="Aplica filtro passa-alta para remover graves indesejados.",
    )
    set_sample_rate_16k: bool = Field(
        default=True,
        description="Ajusta sample rate para 16kHz.",
    )
    isolate_vocals: bool = Field(
        default=False,
        description="Ativa isolamento de voz no áudio.",
    )

    # Heartbeat for orphan detection
    last_heartbeat: Optional[str] = Field(
        default=None,
        description="Marca de vida do worker responsável pelo job (uso interno).",
    )

    class Config:
        json_encoders = {**StandardJob.Config.json_encoders}

    @classmethod
    def create_new(cls, filename: str, **kwargs) -> "AudioNormJob":
        from common.job_utils.models import generate_job_id
        unique_str = f"{filename}_{now_brazil().isoformat()}"
        job_id = generate_job_id(unique_str, prefix="an_")

        job = cls(
            id=job_id,
            filename=filename,
            **kwargs,
        )
        job.add_stage("processing", "Audio normalization")
        job.mark_as_queued()
        return job

    def update_heartbeat(self):
        self.last_heartbeat = now_brazil().isoformat()

    @property
    def is_orphaned(self) -> bool:
        if not self.last_heartbeat or self.is_terminal:
            return False
        last = now_brazil().isoformat()
        from datetime import timedelta
        try:
            from common.datetime_utils import now_brazil as _now
            elapsed = (_now() - now_brazil().fromisoformat(self.last_heartbeat.replace('Z', '+00:00'))).total_seconds() / 60
            return elapsed > 30
        except Exception:
            return False

    @property
    def processing_operations(self) -> list[str]:
        ops = []
        if self.remove_noise:
            ops.append("noise_reduction")
        if self.convert_to_mono:
            ops.append("mono_conversion")
        if self.apply_highpass_filter:
            ops.append("highpass_filter")
        if self.set_sample_rate_16k:
            ops.append("sample_rate_16k")
        if self.isolate_vocals:
            ops.append("vocal_isolation")
        return ops


class DeleteJobResponse(BaseModel):
    message: str = Field(..., description="Resultado da exclusão do job.")
    job_id: str = Field(..., description="ID do job removido.")
    files_deleted: int = Field(..., ge=0, description="Quantidade de arquivos removidos.")


class HeartbeatResponse(BaseModel):
    id: str = Field(..., description="ID do job atualizado.")
    status: str = Field(..., description="Status do heartbeat.", examples=["ok"])
    last_heartbeat: Optional[str] = Field(
        default=None,
        description="Timestamp ISO 8601 do último heartbeat gravado.",
    )


class QueueInfoResponse(BaseModel):
    status: str = Field(..., description="Resultado da consulta da fila.", examples=["success"])
    queue: Dict[str, Any] = Field(
        default_factory=dict,
        description="Informações atuais da fila de processamento.",
    )


class AdminStatsResponse(BaseModel):
    total_jobs: int = Field(default=0, ge=0, description="Total de jobs armazenados.")
    by_status: Dict[str, int] = Field(
        default_factory=dict,
        description="Contagem de jobs agrupada por status.",
    )
    cache: Dict[str, Any] = Field(
        default_factory=dict,
        description="Métricas de cache e arquivos temporários.",
    )


class CleanupResponse(BaseModel):
    jobs_removed: int = Field(default=0, ge=0, description="Quantidade de jobs removidos.")
    files_deleted: int = Field(default=0, ge=0, description="Quantidade de arquivos removidos.")
    space_freed_mb: float = Field(default=0.0, ge=0.0, description="Espaço liberado em MB.")
    errors: List[str] = Field(default_factory=list, description="Lista de erros encontrados na limpeza.")
    redis_flushed: Optional[bool] = Field(
        default=None,
        description="Indica se o Redis foi totalmente limpo em modo profundo.",
    )
    message: Optional[str] = Field(default=None, description="Resumo textual da limpeza executada.")


class RootEndpointsResponse(BaseModel):
    health: str = Field(..., description="Endpoint de health check do serviço.")
    docs: str = Field(..., description="Endpoint da interface Swagger/OpenAPI.")
    jobs: Dict[str, str] = Field(
        default_factory=dict,
        description="Operações principais relacionadas a jobs de normalização.",
    )
    admin: Dict[str, str] = Field(
        default_factory=dict,
        description="Operações administrativas do serviço.",
    )


class RootResponse(BaseModel):
    service: str = Field(..., description="Nome amigável do serviço.")
    version: str = Field(..., description="Versão atual da API.")
    status: str = Field(..., description="Estado resumido do serviço.", examples=["running"])
    description: str = Field(..., description="Resumo do propósito do serviço.")
    endpoints: RootEndpointsResponse = Field(
        ...,
        description="Catálogo resumido dos principais endpoints públicos.",
    )


class HealthCheckComponent(BaseModel):
    status: str = Field(..., description="Resultado da checagem do componente.")
    message: Optional[str] = Field(
        default=None,
        description="Mensagem complementar quando houver aviso ou erro.",
    )
    free_gb: Optional[float] = Field(
        default=None,
        description="Espaço livre em disco, em gigabytes.",
    )
    percent_free: Optional[float] = Field(
        default=None,
        description="Percentual de espaço livre em disco.",
    )
    version: Optional[str] = Field(
        default=None,
        description="Versão detectada da dependência checada, quando aplicável.",
    )


class HealthResponse(BaseModel):
    status: str = Field(..., description="Status geral do serviço.", examples=["healthy"])
    service: str = Field(..., description="Nome técnico do serviço.", examples=["audio-normalization"])
    version: str = Field(..., description="Versão atual da API.")
    timestamp: str = Field(..., description="Timestamp ISO-8601 da verificação.")
    checks: Dict[str, HealthCheckComponent] = Field(
        default_factory=dict,
        description="Detalhamento das checagens executadas durante o health check.",
    )


# Backward compatibility aliases
Job = AudioNormJob
AudioProcessingRequest = AudioNormJob