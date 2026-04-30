"""
API Routes for Make-Video Service.

Segue princípios SOLID:
- Single Responsibility: Cada rota tem uma responsabilidade clara
- Separation of Concerns: Rotas apenas recebem requests e delegam
"""

from pathlib import Path
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Depends
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
    status_code=202,
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
):
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
        # Rate limiting é verificado no main.py

        # Sanitizar query
        sanitized_query = QueryValidator.sanitize(query)
        if not QueryValidator.is_valid(sanitized_query):
            raise HTTPException(
                status_code=HttpStatusCodes.BAD_REQUEST,
                detail="Query inválida após sanitização (mínimo 3 caracteres)"
            )

        logger.info(f"🚀 DOWNLOAD PIPELINE: '{sanitized_query}' (max: {max_shorts})")

        # Criar job - delegado ao main.py para ter acesso às dependências
        # Retorna apenas info de que precisa ser processado
        return {
            "status": "accepted",
            "message": "Use POST /download/start para iniciar o pipeline",
            "query": sanitized_query,
            "max_shorts": max_shorts,
            "note": "This endpoint is handled by the main application"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro no pipeline de download: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Falha no pipeline: {str(e)}"
        )

@router.post(
    "/make-video",
    status_code=202,
    summary="Prepare video creation job",
    description=(
        "Valida o áudio e os parâmetros de composição e retorna a orientação para iniciar "
        "o processamento real na aplicação principal."
    ),
    response_model=CreateVideoAcceptedResponse,
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
    store: RedisJobStore = Depends(get_redis_store_override),
    job_mgr: JobManager = Depends(get_job_manager_override),
    cache_mgr: CacheManager = Depends(get_cache_manager_override),
    lock_mgr: DistributedLockManager = Depends(get_lock_manager_override),
    api_cli: MicroservicesClient = Depends(get_api_client_override),
):
    """
    🎬 Criar vídeo com áudio + shorts APROVADOS.

    **⚠️ IMPORTANTE:** Este endpoint usa apenas vídeos de `data/approved/videos/`

    **Fluxo:**
    1. Recebe áudio
    2. Pega shorts aleatórios de `data/approved/videos/`
    3. Monta vídeo final com legendas
    """
    try:
        # Rate limiting é verificado no main.py

        # Validar áudio
        MAX_AUDIO_SIZE = 100 * 1024 * 1024  # 100MB

        content = await audio_file.read()

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

        # Validar extensão
        if not AudioFileValidator.is_valid_extension(audio_file.filename):
            raise HTTPException(
                status_code=HttpStatusCodes.BAD_REQUEST,
                detail=f"Formato de áudio não suportado. Use: {', '.join(AudioFileValidator.ALLOWED_EXTENSIONS)}"
            )

        # Validar magic bytes
        if not AudioFileValidator.is_valid_content(content, audio_file.filename):
            raise HTTPException(
                status_code=HttpStatusCodes.BAD_REQUEST,
                detail=f"Invalid audio file. Not a valid {file_ext} audio file."
            )

        # Validar parâmetros
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

        # Retornar info - processamento real é delegado ao main.py
        return {
            "status": "accepted",
            "message": "Use POST /make-video/start para iniciar o processamento",
            "audio_filename": audio_file.filename,
            "max_shorts": max_shorts,
            "aspect_ratio": aspect_ratio,
            "subtitle_language": subtitle_language,
            "subtitle_style": subtitle_style,
            "crop_position": crop_position,
            "note": "This endpoint is handled by the main application"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating video: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create video: {str(e)}"
        )

@router.get(
    "/jobs/{job_id}",
    summary="Compatibility job status",
    description="Rota de compatibilidade que orienta a consulta do status real do job.",
    response_model=JobStatusHintResponse,
)
async def get_job_status(
    job_id: str,
    store: RedisJobStore = Depends(get_redis_store_override),
    job_mgr: JobManager = Depends(get_job_manager_override),
):
    """
    Verificar status de um job (com diagnóstico de saúde).
    """
    try:
        # Delegado ao main.py
        return {
            "job_id": job_id,
            "status": "unknown",
            "note": "Use GET /jobs/{job_id}/status para obter status real"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting job status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/download/{job_id}",
    summary="Compatibility download route",
    description="Rota de compatibilidade que informa qual endpoint deve ser usado para baixar o arquivo real.",
)
async def download_video(
    job_id: str,
    store: RedisJobStore = Depends(get_redis_store_override),
    cache_mgr: CacheManager = Depends(get_cache_manager_override),
):
    """
    Fazer download do vídeo final.
    """
    try:
        # Delegado ao main.py
        raise HTTPException(
            status_code=400,
            detail="Use GET /download/{job_id}/file para baixar o arquivo"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error downloading video: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/jobs",
    summary="Compatibility jobs listing",
    description="Rota de compatibilidade que explica qual endpoint expõe a listagem operacional de jobs.",
    response_model=JobListHintResponse,
)
async def list_jobs(
    status: Optional[str] = Query(
        None,
        description="Filtrar por status do job. Opções comuns: queued, processing, completed, failed.",
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
):
    """
    Listar todos os jobs.
    """
    try:
        # Delegado ao main.py
        return {
            "status": "success",
            "total": 0,
            "jobs": [],
            "note": "Use GET /jobs/list para listagem real"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error listing jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete(
    "/jobs/{job_id}",
    summary="Compatibility delete route",
    description="Rota de compatibilidade que orienta a chamada de exclusão efetiva do job.",
    response_model=DeleteJobHintResponse,
)
async def delete_job(
    job_id: str,
    store: RedisJobStore = Depends(get_redis_store_override),
    job_mgr: JobManager = Depends(get_job_manager_override),
):
    """
    Deletar um job e seus arquivos associados.
    """
    try:
        # Delegado ao main.py
        return {
            "status": "accepted",
            "job_id": job_id,
            "message": "Job deletion request received",
            "note": "Use DELETE /jobs/{job_id}/confirm para deletar"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/cache/stats",
    summary="Compatibility cache stats",
    description="Retorna um schema estável para estatísticas de cache e orienta como obter a leitura real atualizada.",
    response_model=CacheStatsResponse,
)
async def get_cache_stats(
    cache_mgr: CacheManager = Depends(get_cache_manager_override),
):
    """
    Estatísticas do cache de shorts.
    """
    try:
        # Delegado ao main.py
        return {
            "total_shorts": 0,
            "total_size_mb": 0.0,
            "approved_videos": 0,
            "note": "Use GET /cache/stats/refresh para obter estatísticas reais"
        }
    except Exception as e:
        logger.error(f"❌ Error getting cache stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/health",
    summary="Compatibility health check",
    description="Rota de compatibilidade. Para o diagnóstico completo, use o health check principal exposto pela aplicação.",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Service unhealthy"}},
)
async def health_check():
    """
    Health check endpoint.
    """
    try:
        from common.datetime_utils import now_brazil

        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "service": "make-video",
                "timestamp": now_brazil().isoformat(),
                "note": "Use GET /health/full para health check completo"
            }
        )
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
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
async def root():
    """Informações do serviço."""
    return {
        "service": "make-video",
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
