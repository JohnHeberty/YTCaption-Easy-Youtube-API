"""
API Routes for Make-Video Service.

Segue princípios SOLID:
- Single Responsibility: Cada rota tem uma responsabilidade clara
- Separation of Concerns: Rotas apenas recebem requests e delegam
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import timedelta
from typing import Any

import shortuuid

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Depends, status
from fastapi.responses import FileResponse, JSONResponse

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from ..core.config import get_settings
from ..core.models import (
    AspectRatioOption,
    CacheStatsResponse,
    CreateVideoAcceptedResponse,
    CreateVideoRequest,
    CropPositionOption,
    DeleteJobHintResponse,
    DownloadPipelineAcceptedResponse,
    HealthResponse,
    Job,
    JobListHintResponse,
    JobStatus,
    JobStatusHintResponse,
    RootInfoResponse,
    StageInfo,
    SubtitleStyleOption,
)
from ..core.constants import ProcessingLimits, AspectRatios, FileExtensions, HttpStatusCodes
from ..core.validators import QueryValidator, AudioFileValidator, JobParamsValidator
from ..infrastructure.dependencies import (
    get_redis_store_override,
    get_job_manager_override,
    get_cache_manager_override,
    get_lock_manager_override,
    get_api_client_override,
)
from ..infrastructure.redis_store import MakeVideoJobStore as RedisJobStore
from ..infrastructure.celery_tasks import process_make_video, process_download_pipeline
from ..services.job_manager import JobManager
from ..services.cache_manager import CacheManager
from ..infrastructure.lock_manager import DistributedLockManager
from ..api.api_client import MicroservicesClient

logger = get_logger(__name__)
router = APIRouter()

settings = get_settings()

def _format_duration(seconds: float) -> str:
    """Formata duração em formato legível."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

@router.post(
    "/download",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Prepare shorts download pipeline",
    description=(
        "Valida a query e retorna a orientação para iniciar o pipeline real de download. "
        "Use esta rota quando quiser descobrir quais parâmetros preencher antes de chamar "
        "o endpoint operacional da aplicação principal."
    ),
    response_model=DownloadPipelineAcceptedResponse,
)
async def download_and_validate_shorts(
    query: str = Form(
        ...,
        min_length=3,
        max_length=200,
        description="Termo de busca para coletar shorts.",
        examples=["motivacao", "treino funcional"],
    ),
    max_shorts: int = Form(
        50,
        ge=10,
        le=500,
        description="Quantidade máxima de shorts para baixar e validar.",
        examples=[50, 100],
    ),
    store: RedisJobStore = Depends(get_redis_store_override),
    job_mgr: JobManager = Depends(get_job_manager_override),
    cache_mgr: CacheManager = Depends(get_cache_manager_override),
    lock_mgr: DistributedLockManager = Depends(get_lock_manager_override),
    api_cli: MicroservicesClient = Depends(get_api_client_override),
) -> dict[str, Any]:
    """
    🆕 Pipeline completo de download e validação de shorts.

    **Fluxo:**
    1. 📥 Download → data/raw/shorts/
    2. 🔄 Transform → data/transform/videos/
    3. ✅ Validate → Detecção de legendas
    4. Aprovação: ✅ SEM legendas / ❌ COM legendas
    5. 🧹 Cleanup

    **Retorna:** job_id para monitoramento
    """
    try:
        sanitized_query = QueryValidator.sanitize(query)
        if not QueryValidator.is_valid(sanitized_query):
            raise HTTPException(
                status_code=HttpStatusCodes.BAD_REQUEST,
                detail="Query inválida após sanitização (mínimo 3 caracteres)"
            )

        logger.info(f"🚀 DOWNLOAD PIPELINE: '{sanitized_query}' (max: {max_shorts})")

        job = Job.create_new(
            query=sanitized_query,
            max_shorts=max_shorts,
            subtitle_language="pt",
            subtitle_style="static",
            aspect_ratio="9:16",
            crop_position="center",
        )
        store.save_job(job)

        process_download_pipeline.delay(job_id=job.id)

        return {
            "status": "accepted",
            "message": "Pipeline de download iniciado",
            "job_id": job.id,
            "query": sanitized_query,
            "max_shorts": max_shorts,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro no pipeline de download: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha no pipeline: {str(e)}"
        )

@router.post(
    "/make-video",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Prepare video creation job",
    description=(
        "Valida o áudio e os parâmetros de composição e retorna a orientação para iniciar "
        "o processamento real na aplicação principal."
    ),
    response_model=CreateVideoAcceptedResponse,
)
def _validate_create_video_params(
    content: bytes,
    audio_file: UploadFile,
    max_shorts: int,
    aspect_ratio: str,
    crop_position: str,
    subtitle_style: str,
) -> None:
    """Validate all create_video parameters. Raises HTTPException on failure."""
    MAX_AUDIO_SIZE = 100 * 1024 * 1024

    if len(content) > MAX_AUDIO_SIZE:
        raise HTTPException(
            status_code=HttpStatusCodes.PAYLOAD_TOO_LARGE,
            detail=f"Audio file too large. Max size: 100MB, received: {len(content) / (1024*1024):.1f}MB"
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=HttpStatusCodes.BAD_REQUEST,
            detail="Audio file is empty"
        )

    file_ext = Path(audio_file.filename).suffix.lower()

    if not AudioFileValidator.is_valid_extension(audio_file.filename):
        raise HTTPException(
            status_code=HttpStatusCodes.BAD_REQUEST,
            detail=f"Formato de áudio não suportado. Use: {', '.join(AudioFileValidator.ALLOWED_EXTENSIONS)}"
        )

    if not AudioFileValidator.is_valid_content(content, audio_file.filename):
        raise HTTPException(
            status_code=HttpStatusCodes.BAD_REQUEST,
            detail=f"Invalid audio file. Not a valid {file_ext} audio file."
        )

    if not JobParamsValidator.validate_max_shorts(max_shorts):
        raise HTTPException(
            status_code=HttpStatusCodes.BAD_REQUEST,
            detail=f"max_shorts deve estar entre {ProcessingLimits.MIN_SHORTS_COUNT} e {ProcessingLimits.MAX_SHORTS_COUNT}"
        )

    if not JobParamsValidator.validate_aspect_ratio(aspect_ratio):
        raise HTTPException(
            status_code=HttpStatusCodes.BAD_REQUEST,
            detail=f"aspect_ratio inválido. Use: {', '.join(JobParamsValidator.VALID_ASPECT_RATIOS)}"
        )

    if not JobParamsValidator.validate_crop_position(crop_position):
        raise HTTPException(
            status_code=HttpStatusCodes.BAD_REQUEST,
            detail="crop_position inválido"
        )

    if not JobParamsValidator.validate_subtitle_style(subtitle_style):
        raise HTTPException(
            status_code=HttpStatusCodes.BAD_REQUEST,
            detail="subtitle_style inválido"
        )


async def create_video(
    audio_file: UploadFile = File(
        ...,
        description="Arquivo de áudio (máximo 100MB). Formatos aceitos: .mp3, .wav, .m4a, .ogg.",
    ),
    max_shorts: int = Form(
        10,
        ge=10,
        le=500,
        description="Quantidade de shorts usados na composição final.",
        examples=[10, 30, 100],
    ),
    subtitle_language: str = Form(
        "pt",
        description="Idioma da legenda. Opções recomendadas: pt, en, es.",
        examples=["pt", "en", "es"],
    ),
    subtitle_style: SubtitleStyleOption = Form(
        SubtitleStyleOption.STATIC,
        description="Estilo da legenda: static, dynamic ou minimal.",
        examples=["static", "dynamic", "minimal"],
    ),
    aspect_ratio: AspectRatioOption = Form(
        AspectRatioOption.VERTICAL,
        description="Aspect ratio do vídeo: 9:16, 16:9, 1:1 ou 4:5.",
        examples=["9:16", "16:9", "1:1", "4:5"],
    ),
    crop_position: CropPositionOption = Form(
        CropPositionOption.CENTER,
        description="Posição do crop no frame: center, top ou bottom.",
        examples=["center", "top", "bottom"],
    ),
    hook_text: str | None = Form(
        None,
        description="Texto do title card (FIX-ERROS Fase 1). Se definido, cria title card de 0.2s.",
    ),
    burn_subtitles: bool = Form(
        True,
        description="Queimar legendas no conteúdo (FIX-ERROS Fase 2). False = sem legendas.",
    ),
    store: RedisJobStore = Depends(get_redis_store_override),
    job_mgr: JobManager = Depends(get_job_manager_override),
    cache_mgr: CacheManager = Depends(get_cache_manager_override),
    lock_mgr: DistributedLockManager = Depends(get_lock_manager_override),
    api_cli: MicroservicesClient = Depends(get_api_client_override),
) -> dict[str, Any]:
    """
    🎬 Criar vídeo com áudio + shorts APROVADOS.

    **⚠️ IMPORTANTE:** Este endpoint usa apenas vídeos de `data/approved/videos/`

    **Fluxo:**
    1. Recebe áudio
    2. Pega shorts aleatórios de `data/approved/videos/`
    3. Monta vídeo final com legendas
    """
    try:
        content = await audio_file.read()

        _validate_create_video_params(
            content, audio_file, max_shorts, aspect_ratio, crop_position, subtitle_style
        )

        file_ext = Path(audio_file.filename).suffix.lower()

        job_id = f"mv_{shortuuid.ShortUUID().random(length=10)}"

        audio_path = Path(settings['audio_upload_dir']) / f"{job_id}{file_ext}"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(content)

        job = Job.create_new(
            audio_file=str(audio_path),
            max_shorts=max_shorts,
            subtitle_language=subtitle_language,
            subtitle_style=subtitle_style,
            aspect_ratio=aspect_ratio,
            crop_position=crop_position,
            hook_text=hook_text,
            burn_subtitles=burn_subtitles,
        )
        job.id = job_id
        store.save_job(job)

        process_make_video.delay(job_id=job.id)

        return {
            "status": "accepted",
            "message": "Processamento de vídeo iniciado",
            "job_id": job.id,
            "audio_filename": audio_file.filename,
            "max_shorts": max_shorts,
            "aspect_ratio": aspect_ratio,
            "subtitle_language": subtitle_language,
            "subtitle_style": subtitle_style,
            "crop_position": crop_position,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating video: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create video: {str(e)}"
        )

@router.get(
    "/jobs/{job_id}",
    summary="Get job status",
    description="Retorna o status atual de um job de processamento.",
    response_model=JobStatusHintResponse,
)
async def get_job_status(
    job_id: str,
    store: RedisJobStore = Depends(get_redis_store_override),
    job_mgr: JobManager = Depends(get_job_manager_override),
) -> dict[str, Any]:
    try:
        job = store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        return {
            "job_id": job.id,
            "status": job.status.value if hasattr(job.status, 'value') else str(job.status),
            "progress": job.progress,
            "stages": {k: v.model_dump() if hasattr(v, 'model_dump') else v for k, v in job.stages.items()},
            "result": (getattr(job, 'result', None) or None),
            "error": getattr(job, 'error', None),
            "created_at": job.created_at.isoformat() if hasattr(job.created_at, 'isoformat') else str(job.created_at),
            "updated_at": getattr(job, 'updated_at', None).isoformat() if hasattr(job, 'updated_at') and getattr(job, 'updated_at', None) and hasattr(getattr(job, 'updated_at'), 'isoformat') else str(getattr(job, 'updated_at', '')),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting job status: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/download/{job_id}",
    summary="Download video file",
    description="Faz o download do arquivo de vídeo final de um job completo.",
)
async def download_video(
    job_id: str,
    store: RedisJobStore = Depends(get_redis_store_override),
    cache_mgr: CacheManager = Depends(get_cache_manager_override),
) -> FileResponse:
    try:
        job = store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        if job.status != JobStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job is not completed yet. Status: {job.status.value if hasattr(job.status, 'value') else job.status}"
            )

        output_path = Path(settings['output_dir']) / f"{job_id}_final.mp4"
        if not output_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found on disk")

        return FileResponse(
            path=str(output_path),
            media_type="video/mp4",
            filename=f"{job_id}_final.mp4",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error downloading video: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/jobs",
    summary="List jobs",
    description="Lista todos os jobs de processamento.",
    response_model=JobListHintResponse,
)
async def list_jobs(
    status: str | None = Query(
        None,
        description="Filtrar por status do job.",
        examples=["queued", "processing", "completed", "failed"],
    ),
    limit: int = Query(
        50,
        ge=1,
        le=500,
        description="Quantidade máxima de jobs retornados.",
        examples=[50, 100],
    ),
    store: RedisJobStore = Depends(get_redis_store_override),
    job_mgr: JobManager = Depends(get_job_manager_override),
) -> dict[str, Any]:
    try:
        jobs = store.list_jobs(limit=limit)

        if status:
            jobs = [j for j in jobs if hasattr(j.status, 'value') and j.status.value == status]

        return {
            "status": "success",
            "total": len(jobs),
            "jobs": [j.model_dump() for j in jobs],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error listing jobs: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete(
    "/jobs/{job_id}",
    summary="Delete job",
    description="Deleta um job e seus arquivos associados.",
    response_model=DeleteJobHintResponse,
)
async def delete_job(
    job_id: str,
    store: RedisJobStore = Depends(get_redis_store_override),
    job_mgr: JobManager = Depends(get_job_manager_override),
) -> dict[str, Any]:
    try:
        job = store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        store.delete_job(job_id)

        output_path = Path(settings['output_dir']) / f"{job_id}_final.mp4"
        if output_path.exists():
            output_path.unlink()

        return {
            "status": "deleted",
            "job_id": job_id,
            "message": "Job e arquivos associados removidos com sucesso",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting job: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/cache/stats",
    summary="Cache statistics",
    description="Retorna estatísticas reais do cache de shorts e vídeos aprovados.",
    response_model=CacheStatsResponse,
)
async def get_cache_stats(
    cache_mgr: CacheManager = Depends(get_cache_manager_override),
) -> dict[str, Any]:
    try:
        stats = cache_mgr.get_stats()
        return {
            "total_shorts": stats.get("total_shorts", 0),
            "total_size_mb": stats.get("total_size_mb", 0.0),
            "approved_videos": stats.get("approved_videos", 0),
        }
    except Exception as e:
        logger.error(f"❌ Error getting cache stats: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/health",
    summary="Compatibility health check",
    description="Rota de compatibilidade. Para o diagnóstico completo, use o health check principal exposto pela aplicação.",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Service unhealthy"}},
)
async def health_check() -> JSONResponse:
    """
    Health check endpoint.
    """
    try:
        from common.datetime_utils import now_brazil

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "healthy",
                "service": "make-video-clip",
                "timestamp": now_brazil().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": now_brazil().isoformat()
            }
        )

@router.get(
    "/",
    summary="Compatibility service info",
    description="Resumo do serviço com foco em descoberta rápida da API pública.",
    response_model=RootInfoResponse,
)
async def root() -> dict[str, Any]:
    """Informações do serviço."""
    return {
        "service": "make-video-clip",
        "version": "2.0.0",
        "description": "Orquestra criação de vídeos a partir de áudio + shorts + legendas",
        "architecture": {
            "pattern": "SOLID + Clean Architecture",
            "refactored": True,
            "date": "2025-04-29"
        },
        "endpoints": {
            "system": ["GET /", "GET /health", "GET /metrics"],
            "workflow": ["POST /download", "POST /make-video"],
            "jobs": ["GET /jobs", "GET /jobs/{job_id}", "DELETE /jobs/{job_id}"],
            "cache": ["GET /cache/stats", "POST /cache/cleanup"],
            "admin": ["GET /admin/stats", "POST /admin/cleanup"]
        },
        "documentation": "Ver PLAN/make-video/PLAN.md"
    }
