from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import Depends
from common.datetime_utils import now_brazil
from common.fastapi_utils import create_service_app, create_api_key_dependency
from common.log_utils import setup_structured_logging, get_logger

from app.services.video_downloader import YDLPVideoDownloader
from app.infrastructure.redis_store import VideoDownloadJobStore
from app.infrastructure.celery_tasks import download_video_task
from app.infrastructure.dependencies import (
    get_job_store, get_downloader, get_settings_dep, _get_settings,
)
from app.core.models import RootResponse, VideoDownloadJob
from app.core.config import get_settings
from app.api import jobs_router, admin_router, health_router

settings = get_settings()
verify_api_key = create_api_key_dependency(api_key=settings.api_key)
setup_structured_logging(
    service_name="video-downloader",
    log_level=settings.log_level,
    log_dir=settings.log_dir,
    json_format=True,
)
logger = get_logger(__name__)

job_store = get_job_store()
downloader = get_downloader()
redis_url = settings.redis_url


@asynccontextmanager
async def lifespan(app: Any) -> AsyncGenerator[None, None]:
    try:
        _store = get_job_store()
        await _store.start_cleanup_task()
        logger.info("Video Download Service iniciado com sucesso")
    except Exception as e:
        logger.error("Erro durante inicialização: %s", e)
        raise

    yield

    try:
        _store = get_job_store()
        await _store.stop_cleanup_task()
        logger.info("Video Download Service parado graciosamente")
    except Exception as e:
        logger.error("Erro durante shutdown: %s", e)


app = create_service_app(
    service_name="video-downloader",
    title="Video Download Service",
    description="Microserviço com Celery + Redis para download de vídeos com cache de 24h",
    version="3.0.0",
    settings=settings,
    lifespan=lifespan,
    body_size_mb=100,
    dependencies=[Depends(verify_api_key)],
    setup_routers=lambda a: (
        a.include_router(jobs_router),
        a.include_router(admin_router),
        a.include_router(health_router),
    ),
)


@app.get(
    "/",
    summary="Service info",
    description="Retorna a visão geral do serviço e o catálogo resumido dos endpoints públicos.",
    response_model=RootResponse,
)
async def root() -> dict[str, Any]:
    return {
        "service": "Video Downloader Service",
        "version": "3.0.0",
        "status": "running",
        "description": "Microserviço com Celery + Redis para download de vídeos do YouTube",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "jobs": {
                "create": "POST /jobs",
                "get": "GET /jobs/{job_id}",
                "list": "GET /jobs",
                "download": "GET /jobs/{job_id}/download",
                "delete": "DELETE /jobs/{job_id}",
                "orphaned": "GET /jobs/orphaned",
                "orphaned_cleanup": "POST /jobs/orphaned/cleanup"
            },
            "admin": {
                "stats": "GET /admin/stats",
                "queue": "GET /admin/queue",
                "cleanup": "POST /admin/cleanup"
            },
            "user_agents": {
                "stats": "GET /user-agents/stats",
                "reset": "POST /user-agents/reset/{user_agent_id}"
            }
        }
    }


def submit_celery_task(job: VideoDownloadJob) -> Any:
    """Submete job para o Celery"""
    job_dict = job.model_dump(mode="json")

    task = download_video_task.apply_async(
        args=[job_dict],
        task_id=job.id
    )

    return task


def execute_pipeline_background(job: VideoDownloadJob) -> None:
    """Executa pipeline em background (fallback se Celery não disponível)"""
    import asyncio
    from common.job_utils.models import JobStatus

    async def _run() -> None:
        try:
            _store = get_job_store()
            _downloader = get_downloader()

            job.status = JobStatus.PROCESSING
            _store.update_job(job)

            result_job = _downloader.download(job)
            _store.update_job(result_job)

            logger.info(f"Pipeline background concluído: {result_job.id} -> {result_job.status}")
        except Exception as e:
            logger.error(f"Erro no pipeline background: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            _store.update_job(job)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_run())
    loop.close()