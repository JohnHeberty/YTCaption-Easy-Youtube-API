import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from app.api.schemas import (
    AdminCleanupResponse,
    AdminOrphanCleanupResponse,
    AdminStatsResponse,
    QueueInfoResponse,
)
from app.core.config import get_core
from app.domain.interfaces import IJobStore
from app.infrastructure.dependencies import job_store
from app.shared.admin_cleanup_service import AdminCleanupService

logger = get_logger(__name__)
settings = get_core()

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post(
    "/cleanup",
    summary="Manual cleanup",
    description=(
        "Executa limpeza administrativa do serviço. Use `deep=true` para limpeza total "
        "(factory reset de Redis, arquivos temporários e modelos locais) e "
        "`purge_celery_queue=true` para remover também tasks pendentes da fila do Celery."
    ),
    response_model=AdminCleanupResponse,
    responses={500: {"description": "Internal server error"}},
)
async def manual_cleanup(
    deep: bool = Query(
        False,
        description="Quando true, executa limpeza profunda com FLUSHDB, remoção de artefatos e modelos locais.",
        examples=[False, True],
    ),
    purge_celery_queue: bool = Query(
        False,
        description="Quando true, remove também tasks pendentes e resultados armazenados do Celery.",
        examples=[False, True],
    ),
    job_store: IJobStore = Depends(job_store),
):
    """Perform system cleanup: basic (expired jobs only) or total (factory reset)."""
    cleanup_type = "TOTAL" if deep else "básica"
    logger.warning(f"🔥 Iniciando limpeza {cleanup_type} SÍNCRONA (purge_celery={purge_celery_queue})")

    try:
        cleanup_svc = AdminCleanupService(dict(get_core()))
        if deep:
            result = await cleanup_svc.deep_cleanup(
                job_store.redis, purge_celery_queue=purge_celery_queue
            )
        else:
            result = await cleanup_svc.basic_cleanup(job_store.redis)

        logger.info(f"✅ Limpeza {cleanup_type} CONCLUÍDA com sucesso")
        return result

    except Exception as e:
        logger.error(f"❌ ERRO na limpeza {cleanup_type}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao fazer cleanup: {str(e)}")


@router.get(
    "/stats",
    summary="Get stats",
    description="Retorna estatísticas agregadas do Redis e métricas de cache/artefatos locais do serviço.",
    response_model=AdminStatsResponse,
)
async def get_stats(job_store: IJobStore = Depends(job_store)):
    """Retrieve transcription service statistics including job counts and disk usage."""
    stats = job_store.get_stats()

    upload_path = Path(settings.get('upload_dir', './data/uploads'))
    transcription_path = Path(settings.get('transcription_dir', './data/transcriptions'))

    total_files = 0
    total_size = 0

    for path in [upload_path, transcription_path]:
        if path.exists():
            files = list(path.iterdir())
            total_files += len(files)
            total_size += sum(f.stat().st_size for f in files if f.is_file())

    stats["cache"] = {
        "files_count": total_files,
        "total_size_mb": round(total_size / (1024 * 1024), 2)
    }

    return stats


@router.get(
    "/queue",
    summary="Get queue info",
    description="Inspeciona a fila do Celery e retorna estado resumido de processamento assíncrono.",
    response_model=QueueInfoResponse,
    responses={500: {"description": "Internal server error"}},
)
async def get_queue_info_endpoint(job_store: IJobStore = Depends(job_store)):
    """Retrieve Celery queue information for the transcription service."""
    try:
        queue_info = await job_store.get_queue_info()

        return {
            "status": "success",
            "queue": queue_info
        }

    except Exception as e:
        logger.error(f"Error getting queue info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get queue info: {str(e)}")


@router.post(
    "/cleanup-orphans",
    summary="Cleanup orphan jobs",
    description="Procura jobs órfãos e remove artefatos inconsistentes gerados por execuções interrompidas.",
    response_model=AdminOrphanCleanupResponse,
    responses={500: {"description": "Internal server error"}},
)
async def cleanup_orphan_jobs_endpoint(job_store: IJobStore = Depends(job_store)):
    """Clean up orphaned transcription jobs using the OrphanJobCleaner."""
    try:
        from app.shared.orphan_cleaner import OrphanJobCleaner

        cleaner = OrphanJobCleaner(job_store)
        stats = await cleaner.cleanup_orphans()

        return JSONResponse(content={
            "success": True,
            "stats": stats,
            "timestamp": now_brazil().isoformat()
        })

    except Exception as e:
        logger.error(f"❌ Erro na limpeza de órfãos: {e}")
        return JSONResponse(
            content={
                "success": False,
                "error": str(e)
            },
            status_code=500
        )