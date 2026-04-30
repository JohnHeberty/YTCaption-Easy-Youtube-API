"""
Make-Video Service - FastAPI Application (Refactored v2.0)

Serviço refatorado seguindo princípios SOLID e PYTHONIC.
Correções críticas:
- asyncio.run() → await em contexto async
- Parsing manual Redis → redis.from_url()
- Rate limiting duplicado → usar common/
- God class dividida em módulos especializados

Arquitetura:
- app/api/routes.py - Endpoints FastAPI
- app/services/video_builder.py - Construção de vídeos
- app/services/job_manager.py - Gerenciamento de jobs
- app/services/cache_manager.py - Cache de shorts
- app/infrastructure/lock_manager.py - Locks distribuídos
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Common library imports
from common.datetime_utils import now_brazil
from common.redis_utils import ResilientRedisStore
from common.exception_handlers import setup_exception_handlers
from common.log_utils import setup_structured_logging, get_logger

from .core.config import get_settings
from .core.models import HealthResponse, Job, JobStatus, RootInfoResponse, StageInfo
from .core.constants import ProcessingLimits, AspectRatios, FileExtensions, HttpStatusCodes
from .infrastructure.redis_store import MakeVideoJobStore as RedisJobStore
from .infrastructure.lock_manager import DistributedLockManager
from .services.job_manager import JobManager
from .services.cache_manager import CacheManager
from .api.api_client import MicroservicesClient
from .api.routes import router as api_router
from .infrastructure.dependencies import (
    get_redis_store, get_job_manager, get_cache_manager,
    get_lock_manager, get_api_client,
)

# Setup logging
setup_structured_logging("make-video")
logger = get_logger(__name__)

# Settings
settings = get_settings()

# ============================================================================
# GLOBAL INSTANCES (inicializados no lifespan)
# ============================================================================
redis_store: Optional[RedisJobStore] = None
job_manager: Optional[JobManager] = None
cache_manager: Optional[CacheManager] = None
lock_manager: Optional[DistributedLockManager] = None
api_client: Optional[MicroservicesClient] = None
_scheduler = None


# ============================================================================
# LIFECYCLE
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — replaces deprecated @app.on_event."""
    global redis_store, job_manager, cache_manager, lock_manager, api_client, _scheduler

    # ---- startup ----
    logger.info("🚀 Make-Video Service starting...")

    # Criar diretórios necessários
    for dir_path in [
        settings['audio_upload_dir'],
        settings['shorts_cache_dir'],
        '/tmp/make-video-temp',
        settings['output_dir'],
        settings['logs_dir'],
    ]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    # Inicializar componentes usando DI factory calls
    redis_url = settings['redis_url']
    logger.info(f"🔌 Connecting to Redis: {redis_url}")

    redis_store = get_redis_store()
    job_manager = get_job_manager()
    cache_manager = get_cache_manager()
    lock_manager = get_lock_manager()
    api_client = get_api_client()

    # Iniciar cleanup task automatico (Redis)
    await redis_store.start_cleanup_task() if hasattr(redis_store, 'start_cleanup_task') else None
    logger.info("Redis cleanup task started")

    # Iniciar cron de limpeza de vídeos órfãos
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        _scheduler = AsyncIOScheduler()
        _scheduler.add_job(
            cleanup_orphaned_videos_cron,
            trigger=IntervalTrigger(minutes=5),
            id='cleanup_orphaned_videos',
            name='Cleanup orphaned videos every 5 minutes',
            replace_existing=True,
        )
        _scheduler.start()
        logger.info("🧹 Orphaned videos cleanup cron started")
    except Exception as e:
        logger.error("❌ Failed to start APScheduler: %s", e, exc_info=True)

    logger.info("✅ Make-Video Service ready!")
    logger.info("   ├─ Redis: %s", redis_url)
    logger.info("   ├─ YouTube Search: %s", settings['youtube_search_url'])
    logger.info("   ├─ Video Downloader: %s", settings['video_downloader_url'])
    logger.info("   └─ Audio Transcriber: %s", settings['audio_transcriber_url'])

    yield

    # ---- shutdown ----
    logger.info("🛑 Make-Video Service shutting down...")

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        logger.info("🧹 Scheduler stopped")

    await redis_store.stop_cleanup_task()
    await lock_manager.close()

    logger.info("✅ Make-Video Service stopped cleanly")


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Make-Video Service",
    description="Orquestra criação de vídeos a partir de áudio + shorts + legendas",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir rotas da API
app.include_router(api_router)

# Exception handlers
setup_exception_handlers(app, debug=settings.get('debug', False))


# ============================================================================
# CRON JOB FUNCTIONS
# ============================================================================

async def cleanup_orphaned_videos_cron():
    """Cron job: Limpa vídeos órfãos a cada 5 minutos."""
    try:
        logger.info("🧹 CRON: Starting orphaned videos cleanup...")

        from .pipeline import VideoPipeline
        pipeline = VideoPipeline()
        pipeline.cleanup_orphaned_files(max_age_minutes=10)

        logger.info("🧹 CRON: Orphaned videos cleanup completed")
    except Exception as e:
        logger.error(f"❌ CRON: Orphaned videos cleanup failed: {e}", exc_info=True)


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get(
    "/health",
    summary="Health check",
    description=(
        "Executa a verificação principal do serviço e agrega o estado das dependências "
        "necessárias para a criação de vídeos."
    ),
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Service unhealthy"}},
)
async def health_check():
    """Health check endpoint."""
    try:
        from .infrastructure.health_checker import get_health_checker

        health_checker = get_health_checker()

        if health_checker.redis_store is None:
            health_checker.set_dependencies(redis_store, api_client, settings)

        results = await health_checker.check_all(include_celery=False)
        all_healthy = health_checker.is_healthy(results)

        checks_dict = {
            name: result.to_dict()
            for name, result in results.items()
        }

        return JSONResponse(
            status_code=200 if all_healthy else 503,
            content={
                "status": "healthy" if all_healthy else "unhealthy",
                "service": "make-video",
                "version": "2.0.0",
                "checks": checks_dict,
                "timestamp": now_brazil().isoformat()
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


# ============================================================================
# METRICS
# ============================================================================

@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    try:
        import shutil

        # Disk metrics
        try:
            temp_stat = shutil.disk_usage('/tmp/make-video-temp')
            disk_free_gb = temp_stat.free / (1024**3)
            disk_used_pct = (temp_stat.used / temp_stat.total) * 100
        except:
            disk_free_gb = 0
            disk_used_pct = 100

        # Job stats
        job_stats = job_manager.get_stats() if job_manager else {}

        metrics_output = f"""# HELP makevideo_jobs_total Total jobs
# TYPE makevideo_jobs_total counter
makevideo_jobs_queued {job_stats.get('queued', 0)}
makevideo_jobs_processing {job_stats.get('processing', 0)}
makevideo_jobs_completed {job_stats.get('completed', 0)}
makevideo_jobs_failed {job_stats.get('failed', 0)}

# HELP makevideo_disk_free_gb Free disk space in GB
# TYPE makevideo_disk_free_gb gauge
makevideo_disk_free_gb {{path="{'/tmp/make-video-temp'}"}} {disk_free_gb:.2f}

# HELP makevideo_disk_used_percent Disk usage percentage
# TYPE makevideo_disk_used_percent gauge
makevideo_disk_used_percent {{path="{'/tmp/make-video-temp'}"}} {disk_used_pct:.2f}
"""

        from fastapi.responses import Response
        return Response(content=metrics_output, media_type="text/plain")

    except Exception as e:
        logger.error(f"❌ Metrics error: {e}", exc_info=True)
        from fastapi.responses import Response
        return Response(content=f"# Error generating metrics: {e}", media_type="text/plain")


# ============================================================================
# ROOT
# ============================================================================

@app.get(
    "/",
    summary="Service info",
    description="Retorna visão geral do serviço, arquitetura e catálogo resumido de endpoints.",
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
        "fixes": {
            "P0_asyncio_run": "Removido - agora usa await",
            "P0_redis_parsing": "Usa redis.from_url()",
            "P0_common_library": "Adicionado -e ./common",
            "P1_god_class": "Dividido em VideoBuilder, JobManager, CacheManager",
            "P1_rate_limiting": "Usa common/",
        },
        "endpoints": {
            "system": ["GET /", "GET /health", "GET /metrics"],
            "workflow": ["POST /download", "POST /make-video"],
            "jobs": ["GET /jobs", "GET /jobs/{job_id}", "DELETE /jobs/{job_id}"],
            "cache": ["GET /cache/stats"],
            "admin": ["GET /admin/stats", "POST /admin/cleanup"]
        },
        "documentation": "Ver PLAN/make-video/PLAN.md"
    }


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8005,
        reload=True,
        log_level="info"
    )
