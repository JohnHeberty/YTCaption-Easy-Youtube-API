import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from common.datetime_utils import now_brazil
from common.log_utils import setup_structured_logging, get_logger
from common.fastapi_utils import create_service_app

from .core.config import get_settings
from .core.models import HealthResponse, Job, JobStatus, RootInfoResponse, StageInfo
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

setup_structured_logging("make-video")
logger = get_logger(__name__)
settings = get_settings()

redis_store: Optional[RedisJobStore] = None
job_manager: Optional[JobManager] = None
cache_manager: Optional[CacheManager] = None
lock_manager: Optional[DistributedLockManager] = None
api_client: Optional[MicroservicesClient] = None
_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_store, job_manager, cache_manager, lock_manager, api_client, _scheduler

    logger.info("Make-Video Service starting...")

    for dir_path in [
        settings['audio_upload_dir'],
        settings['shorts_cache_dir'],
        '/tmp/make-video-temp',
        settings['output_dir'],
        settings['logs_dir'],
    ]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    redis_store = get_redis_store()
    job_manager = get_job_manager()
    cache_manager = get_cache_manager()
    lock_manager = get_lock_manager()
    api_client = get_api_client()

    await redis_store.start_cleanup_task() if hasattr(redis_store, 'start_cleanup_task') else None

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
    except Exception as e:
        logger.error("Failed to start APScheduler: %s", e, exc_info=True)

    logger.info("Make-Video Service ready!")
    yield

    logger.info("Make-Video Service shutting down...")
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
    await redis_store.stop_cleanup_task()
    await lock_manager.close()


cors_config = {
    "allow_origins": ["*"],
    "allow_credentials": False,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}


def setup_routers(app):
    app.include_router(api_router)


app = create_service_app(
    service_name="make-video",
    title="Make-Video Service",
    description="Orquestra criação de vídeos a partir de áudio + shorts + legendas",
    version="2.0.0",
    settings=settings,
    lifespan=lifespan,
    setup_routers=setup_routers,
    cors_config=cors_config,
)


async def cleanup_orphaned_videos_cron():
    try:
        from .pipeline import VideoPipeline
        pipeline = VideoPipeline()
        pipeline.cleanup_orphaned_files(max_age_minutes=10)
    except Exception as e:
        logger.error("CRON: Orphaned videos cleanup failed: %s", e, exc_info=True)


@app.get(
    "/health",
    summary="Health check",
    description="Executa a verificação principal do serviço e agrega o estado das dependências.",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Service unhealthy"}},
)
async def health_check():
    try:
        from .infrastructure.health_checker import get_health_checker
        health_checker = get_health_checker()
        if health_checker.redis_store is None:
            health_checker.set_dependencies(redis_store, api_client, settings)
        results = await health_checker.check_all(include_celery=False)
        all_healthy = health_checker.is_healthy(results)
        checks_dict = {name: result.to_dict() for name, result in results.items()}
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
        logger.error("Health check failed: %s", e, exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": now_brazil().isoformat()
            }
        )


@app.get("/metrics")
async def prometheus_metrics():
    try:
        import shutil
        try:
            temp_stat = shutil.disk_usage('/tmp/make-video-temp')
            disk_free_gb = temp_stat.free / (1024**3)
            disk_used_pct = (temp_stat.used / temp_stat.total) * 100
        except:
            disk_free_gb = 0
            disk_used_pct = 100
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
        logger.error("Metrics error: %s", e, exc_info=True)
        from fastapi.responses import Response
        return Response(content=f"# Error generating metrics: {e}", media_type="text/plain")


@app.get(
    "/",
    summary="Service info",
    description="Retorna visão geral do serviço, arquitetura e catálogo resumido de endpoints.",
    response_model=RootInfoResponse,
)
async def root():
    return {
        "service": "make-video",
        "version": "2.0.0",
        "description": "Orquestra criação de vídeos a partir de áudio + shorts + legendas",
        "architecture": {"pattern": "SOLID + Clean Architecture", "refactored": True, "date": "2025-04-29"},
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8005, reload=True, log_level="info")
