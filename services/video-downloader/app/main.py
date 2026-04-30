import os
from contextlib import asynccontextmanager

from common.datetime_utils import now_brazil
from common.log_utils import setup_structured_logging, get_logger
from common.exception_handlers import setup_exception_handlers

from fastapi import FastAPI

from app.services.video_downloader import YDLPVideoDownloader
from app.infrastructure.redis_store import VideoDownloadJobStore
from app.infrastructure.celery_tasks import download_video_task
from app.infrastructure.dependencies import (
    get_job_store, get_downloader, get_settings_dep, _get_settings,
)
from app.shared.exceptions import VideoDownloadException, ServiceException, exception_handler
from app.core.models import RootResponse, VideoDownloadJob
from app.core.config import get_settings
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.body_size import BodySizeMiddleware
from app.api import jobs_router, admin_router, health_router

# Configuração de logging
settings = get_settings()
setup_structured_logging(
    service_name="video-downloader",
    log_level=settings.get('log_level', 'INFO'),
    log_dir=settings.get('log_dir', './logs'),
    json_format=True
)
logger = get_logger(__name__)

# ============================================================================
# LIFECYCLE
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — replaces deprecated @app.on_event."""
    try:
        job_store = get_job_store()
        await job_store.start_cleanup_task()
        logger.info("Video Download Service iniciado com sucesso")
    except Exception as e:
        logger.error("Erro durante inicialização: %s", e)
        raise

    yield

    try:
        job_store = get_job_store()
        await job_store.stop_cleanup_task()
        logger.info("Video Download Service parado graciosamente")
    except Exception as e:
        logger.error("Erro durante shutdown: %s", e)


# Instâncias globais via DI module
app = FastAPI(
    title="Video Download Service",
    description="Microserviço com Celery + Redis para download de vídeos com cache de 24h",
    version="3.0.0",
    lifespan=lifespan,
)

# Setup exception handlers
setup_exception_handlers(app, debug=settings.get('debug', False))

# Exception handlers - mantidos para compatibilidade
app.add_exception_handler(VideoDownloadException, exception_handler)
app.add_exception_handler(ServiceException, exception_handler)

# Rate limiting middleware (per-IP sliding window)
_rl = settings.get('rate_limit', {})
if isinstance(_rl, dict) and _rl.get('enabled', True):
    app.add_middleware(
        RateLimiterMiddleware,
        max_requests=_rl.get('max_requests', 100),
        window_seconds=_rl.get('window_seconds', 60),
    )

# Body size middleware
app.add_middleware(
    BodySizeMiddleware,
    max_size=100 * 1024 * 1024,  # 100MB
)

# Backward-compatible module-level names from DI
job_store = get_job_store()
downloader = get_downloader()
redis_url = settings.redis_url

# Include routers
app.include_router(jobs_router)
app.include_router(admin_router)
app.include_router(health_router)


@app.get(
    "/",
    summary="Service info",
    description="Retorna a visão geral do serviço e o catálogo resumido dos endpoints públicos.",
    response_model=RootResponse,
)
async def root():
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


def submit_celery_task(job: VideoDownloadJob):
    """Submete job para o Celery"""
    job_dict = job.model_dump(mode="json")

    task = download_video_task.apply_async(
        args=[job_dict],
        task_id=job.id
    )

    return task


def execute_pipeline_background(job: VideoDownloadJob):
    """Executa pipeline em background (fallback se Celery não disponível)"""
    import asyncio
    from common.job_utils.models import JobStatus

    async def _run():
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