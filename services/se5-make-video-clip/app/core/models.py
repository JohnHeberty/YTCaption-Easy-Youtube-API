"""
Make-video job model extending StandardJob.

Adds service-specific video composition fields (shorts, subtitles,
aspect ratio, crop position) while inheriting standard lifecycle.
"""
from __future__ import annotations

from enum import Enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
import shortuuid

from common.job_utils.models import StandardJob, JobStatus, StageInfo, StageStatus
from common.datetime_utils import now_brazil


class MakeVideoJob(StandardJob):
    # Input
    audio_file: str | None = None
    query: str | None = None

    # Video parameters
    max_shorts: int = 5
    subtitle_language: str | None = None
    subtitle_style: str | None = None
    aspect_ratio: str = "9:16"
    crop_position: str = "center"
    hook_text: str | None = None
    burn_subtitles: bool = True

    # Video processing stages with detailed tracking
    # Stages are defined in StandardJob.stages dict

    # Audio analysis
    audio_duration: float | None = None
    target_video_duration: float | None = None

    # Error tracking
    error: dict[str, Any] | None = None

    # Results
    result: dict[str, Any] | None = None
    output_file: str | None = None
    output_url: str | None = None

    # json_encoders removed — Pydantic v2 handles datetime natively

    @classmethod
    def create_new(cls, **kwargs) -> MakeVideoJob:
        job_id = f"mv_{shortuuid.ShortUUID().random(length=10)}"

        job = cls(
            id=job_id,
            **kwargs,
        )
        job.add_stage("analyze_audio", "Analyzing audio")
        job.add_stage("load_approved", "Loading approved videos")
        job.add_stage("select_shorts", "Selecting shorts")
        job.add_stage("assemble_video", "Assembling video")
        job.add_stage("generate_subtitles", "Generating subtitles")
        job.add_stage("final_composition", "Final composition")
        job.add_stage("trim_video", "Trimming video")
        job.add_stage("validate_av_sync", "Validating A/V sync")
        job.mark_as_queued()
        return job


class SubtitleStyleOption(str, Enum):
    STATIC = "static"
    DYNAMIC = "dynamic"
    MINIMAL = "minimal"


class AspectRatioOption(str, Enum):
    VERTICAL = "9:16"
    HORIZONTAL = "16:9"
    SQUARE = "1:1"
    PORTRAIT = "4:5"


class CropPositionOption(str, Enum):
    CENTER = "center"
    TOP = "top"
    BOTTOM = "bottom"


# Backward compatibility: re-export legacy model classes


class ShortInfo(BaseModel):
    video_id: str
    duration_seconds: float
    file_path: str
    position_in_video: float
    resolution: str = "1080x1920"
    fps: int = 30


class SubtitleSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str


class JobResult(BaseModel):
    video_url: str
    video_file: str
    file_size: int
    file_size_mb: float
    duration: float
    resolution: str
    aspect_ratio: str
    fps: int
    shorts_used: int
    shorts_list: list[ShortInfo]
    subtitle_segments: int
    processing_time: float


class CreateVideoRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    max_shorts: int = Field(default=100, ge=10, le=500)
    subtitle_language: str = Field(default="pt")
    subtitle_style: SubtitleStyleOption = Field(default=SubtitleStyleOption.DYNAMIC)
    aspect_ratio: AspectRatioOption = Field(default=AspectRatioOption.VERTICAL)
    crop_position: CropPositionOption = Field(default=CropPositionOption.CENTER)
    hook_text: str | None = Field(default=None, description="Texto do title card (FIX-ERROS Fase 1)")
    burn_subtitles: bool = Field(default=True, description="Queimar legendas no conteúdo (FIX-ERROS Fase 2)")


class DownloadPipelineAcceptedResponse(BaseModel):
    status: str = Field(..., description="Status imediato da requisição.", examples=["accepted"])
    message: str = Field(..., description="Mensagem de confirmação do pipeline.")
    job_id: str = Field(..., description="ID do job criado para monitoramento.")
    query: str = Field(..., description="Query sanitizada que será usada no pipeline.")
    max_shorts: int = Field(..., description="Quantidade máxima de shorts considerada no pipeline.")


class CreateVideoAcceptedResponse(BaseModel):
    status: str = Field(..., description="Status imediato da requisição.", examples=["accepted"])
    message: str = Field(..., description="Mensagem de confirmação do processamento.")
    job_id: str = Field(..., description="ID do job criado para monitoramento.")
    audio_filename: str = Field(..., description="Nome do arquivo de áudio validado na entrada.")
    max_shorts: int = Field(..., description="Quantidade máxima de shorts usada na composição final.")
    subtitle_language: str = Field(..., description="Idioma selecionado para as legendas.")
    subtitle_style: SubtitleStyleOption = Field(..., description="Estilo selecionado para a legenda.")
    aspect_ratio: AspectRatioOption = Field(..., description="Aspect ratio informado para o vídeo final.")
    crop_position: CropPositionOption = Field(..., description="Posição do crop aplicada no enquadramento.")


class JobStatusResponse(BaseModel):
    job_id: str = Field(..., description="ID do job consultado.")
    status: str = Field(..., description="Status atual do job.")
    progress: float = Field(default=0.0, description="Progresso do job (0-100).")
    stages: dict[str, Any] = Field(default_factory=dict, description="Estágios do processamento.")
    result: dict[str, Any] | None = Field(default=None, description="Resultado do job quando completo.")
    error: dict[str, Any] | None = Field(default=None, description="Erro do job quando falhou.")
    created_at: str = Field(default="", description="Timestamp de criação.")
    updated_at: str = Field(default="", description="Timestamp da última atualização.")


JobStatusHintResponse = JobStatusResponse


class JobListHintResponse(BaseModel):
    status: str = Field(..., description="Resultado resumido da consulta.")
    total: int = Field(..., ge=0, description="Quantidade de jobs retornados.")
    jobs: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Lista de jobs retornados.",
    )


class DeleteJobHintResponse(BaseModel):
    status: str = Field(..., description="Status imediato da solicitação de exclusão.")
    job_id: str = Field(..., description="ID do job alvo da exclusão.")
    message: str = Field(..., description="Mensagem resumindo a ação aceita.")


class CacheStatsResponse(BaseModel):
    total_shorts: int = Field(..., ge=0, description="Quantidade de shorts presentes no cache.")
    total_size_mb: float = Field(..., ge=0.0, description="Tamanho total do cache, em MB.")
    approved_videos: int = Field(..., ge=0, description="Quantidade de vídeos aprovados disponíveis.")


class RootArchitectureResponse(BaseModel):
    pattern: str = Field(..., description="Padrão arquitetural adotado pelo serviço.")
    refactored: bool = Field(..., description="Indica se o serviço já passou por refatoração estrutural.")
    date: str = Field(..., description="Data de referência da última refatoração informada.")


class RootEndpointsResponse(BaseModel):
    system: list[str] = Field(default_factory=list, description="Endpoints sistêmicos do serviço.")
    workflow: list[str] = Field(default_factory=list, description="Endpoints do fluxo principal de criação de vídeo.")
    jobs: list[str] = Field(default_factory=list, description="Endpoints de consulta e remoção de jobs.")
    cache: list[str] = Field(default_factory=list, description="Endpoints de cache e estatísticas associadas.")
    admin: list[str] = Field(default_factory=list, description="Endpoints administrativos do serviço.")


class RootInfoResponse(BaseModel):
    service: str = Field(..., description="Nome técnico do serviço.")
    version: str = Field(..., description="Versão da API.")
    description: str = Field(..., description="Resumo do papel do serviço dentro do pipeline.")
    architecture: RootArchitectureResponse = Field(..., description="Resumo da arquitetura adotada.")
    fixes: dict[str, str] = Field(
        default_factory=dict,
        description="Resumo das principais correções/refatorações aplicadas ao serviço.",
    )
    endpoints: RootEndpointsResponse = Field(
        ...,
        description="Catálogo resumido das rotas públicas do serviço.",
    )
    documentation: str = Field(..., description="Referência documental complementar do serviço.")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Status geral do serviço.")
    service: str = Field(default="make-video-clip", description="Nome técnico do serviço.")
    version: str | None = Field(default=None, description="Versão atual da API.")
    checks: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Resultado detalhado das checagens do serviço e dependências.",
    )
    dependencies: dict[str, str] = Field(default_factory=dict, description="Dependências resumidas do serviço.")
    storage: dict[str, Any] = Field(default_factory=dict, description="Métricas de armazenamento, quando disponíveis.")
    timestamp: Any | None = Field(default=None, description="Timestamp ISO-8601 da verificação.")
    error: str | None = Field(default=None, description="Erro retornado quando o health check falha integralmente.")
    note: str | None = Field(default=None, description="Orientação adicional para operadores do serviço.")


# Alias for backward compatibility
Job = MakeVideoJob