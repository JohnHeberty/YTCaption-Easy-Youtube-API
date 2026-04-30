"""
Make-video job model extending StandardJob.

Adds service-specific video composition fields (shorts, subtitles,
aspect ratio, crop position) while inheriting standard lifecycle.
"""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
import shortuuid

from common.job_utils.models import StandardJob, JobStatus, StageInfo, StageStatus
from common.datetime_utils import now_brazil


class MakeVideoJob(StandardJob):
    # Input
    audio_file: Optional[str] = None
    query: Optional[str] = None

    # Video parameters
    max_shorts: int = 5
    subtitle_language: Optional[str] = None
    subtitle_style: Optional[str] = None
    aspect_ratio: str = "9:16"
    crop_position: str = "center"

    # Video processing stages with detailed tracking
    # Stages are defined in StandardJob.stages dict

    # Results
    output_file: Optional[str] = None
    output_url: Optional[str] = None

    class Config:
        json_encoders = {**StandardJob.Config.json_encoders}

    @classmethod
    def create_new(cls, **kwargs) -> "MakeVideoJob":
        job_id = f"mv_{shortuuid.ShortUUID().random(length=10)}"

        job = cls(
            id=job_id,
            **kwargs,
        )
        job.add_stage("analyzing_audio", "Analyzing audio")
        job.add_stage("fetching_shorts", "Fetching short videos")
        job.add_stage("downloading_shorts", "Downloading shorts")
        job.add_stage("selecting_shorts", "Selecting best shorts")
        job.add_stage("assembling_video", "Assembling video")
        job.add_stage("generating_subtitles", "Generating subtitles")
        job.add_stage("final_composition", "Final composition")
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
    shorts_list: List[ShortInfo]
    subtitle_segments: int
    processing_time: float


class CreateVideoRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    max_shorts: int = Field(default=100, ge=10, le=500)
    subtitle_language: str = Field(default="pt")
    subtitle_style: SubtitleStyleOption = Field(default=SubtitleStyleOption.DYNAMIC)
    aspect_ratio: AspectRatioOption = Field(default=AspectRatioOption.VERTICAL)
    crop_position: CropPositionOption = Field(default=CropPositionOption.CENTER)


class DownloadPipelineAcceptedResponse(BaseModel):
    status: str = Field(..., description="Status imediato da requisição.", examples=["accepted"])
    message: str = Field(..., description="Orientação sobre o próximo endpoint a ser chamado.")
    query: str = Field(..., description="Query sanitizada que será usada no pipeline.")
    max_shorts: int = Field(..., description="Quantidade máxima de shorts considerada no pipeline.")
    note: str = Field(..., description="Observação indicando que a execução real ocorre na aplicação principal.")


class CreateVideoAcceptedResponse(BaseModel):
    status: str = Field(..., description="Status imediato da requisição.", examples=["accepted"])
    message: str = Field(..., description="Orientação sobre o próximo endpoint a ser chamado.")
    audio_filename: str = Field(..., description="Nome do arquivo de áudio validado na entrada.")
    max_shorts: int = Field(..., description="Quantidade máxima de shorts usada na composição final.")
    subtitle_language: str = Field(..., description="Idioma selecionado para as legendas.")
    subtitle_style: SubtitleStyleOption = Field(..., description="Estilo selecionado para a legenda.")
    aspect_ratio: AspectRatioOption = Field(..., description="Aspect ratio informado para o vídeo final.")
    crop_position: CropPositionOption = Field(..., description="Posição do crop aplicada no enquadramento.")
    note: str = Field(..., description="Observação indicando que a execução real ocorre na aplicação principal.")


class JobStatusHintResponse(BaseModel):
    job_id: str = Field(..., description="ID do job consultado.")
    status: str = Field(..., description="Status retornado pela rota de compatibilidade.")
    note: str = Field(..., description="Orientação para a rota que devolve o status real.")


class JobListHintResponse(BaseModel):
    status: str = Field(..., description="Resultado resumido da consulta.")
    total: int = Field(..., ge=0, description="Quantidade de jobs retornados pela rota de compatibilidade.")
    jobs: List[MakeVideoJob] = Field(
        default_factory=list,
        description="Lista de jobs retornados pela rota de compatibilidade.",
    )
    note: str = Field(..., description="Orientação para a rota de listagem real.")


class DeleteJobHintResponse(BaseModel):
    status: str = Field(..., description="Status imediato da solicitação de exclusão.")
    job_id: str = Field(..., description="ID do job alvo da exclusão.")
    message: str = Field(..., description="Mensagem resumindo a ação aceita.")
    note: str = Field(..., description="Orientação para a rota que executa a exclusão real.")


class CacheStatsResponse(BaseModel):
    total_shorts: int = Field(..., ge=0, description="Quantidade de shorts presentes no cache.")
    total_size_mb: float = Field(..., ge=0.0, description="Tamanho total do cache, em MB.")
    approved_videos: int = Field(..., ge=0, description="Quantidade de vídeos aprovados disponíveis.")
    note: str = Field(..., description="Orientação para obter estatísticas completas e atualizadas.")


class RootArchitectureResponse(BaseModel):
    pattern: str = Field(..., description="Padrão arquitetural adotado pelo serviço.")
    refactored: bool = Field(..., description="Indica se o serviço já passou por refatoração estrutural.")
    date: str = Field(..., description="Data de referência da última refatoração informada.")


class RootEndpointsResponse(BaseModel):
    system: List[str] = Field(default_factory=list, description="Endpoints sistêmicos do serviço.")
    workflow: List[str] = Field(default_factory=list, description="Endpoints do fluxo principal de criação de vídeo.")
    jobs: List[str] = Field(default_factory=list, description="Endpoints de consulta e remoção de jobs.")
    cache: List[str] = Field(default_factory=list, description="Endpoints de cache e estatísticas associadas.")
    admin: List[str] = Field(default_factory=list, description="Endpoints administrativos do serviço.")


class RootInfoResponse(BaseModel):
    service: str = Field(..., description="Nome técnico do serviço.")
    version: str = Field(..., description="Versão da API.")
    description: str = Field(..., description="Resumo do papel do serviço dentro do pipeline.")
    architecture: RootArchitectureResponse = Field(..., description="Resumo da arquitetura adotada.")
    fixes: Dict[str, str] = Field(
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
    service: str = Field(default="make-video", description="Nome técnico do serviço.")
    version: Optional[str] = Field(default=None, description="Versão atual da API.")
    checks: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Resultado detalhado das checagens do serviço e dependências.",
    )
    dependencies: Dict[str, str] = Field(default_factory=dict, description="Dependências resumidas do serviço.")
    storage: Dict[str, Any] = Field(default_factory=dict, description="Métricas de armazenamento, quando disponíveis.")
    timestamp: Optional[Any] = Field(default=None, description="Timestamp ISO-8601 da verificação.")
    error: Optional[str] = Field(default=None, description="Erro retornado quando o health check falha integralmente.")
    note: Optional[str] = Field(default=None, description="Orientação adicional para operadores do serviço.")


# Alias for backward compatibility
Job = MakeVideoJob