import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, Request

from common.log_utils import setup_structured_logging, get_logger
from common.fastapi_utils import create_service_app, create_api_key_dependency

from .core.config import get_settings
from .api.routes import router as api_router
from .infrastructure.dependencies import (
    get_redis_store, get_job_manager, get_cache_manager,
    get_lock_manager, get_api_client,
)

setup_structured_logging("make-video-clip")
logger = get_logger(__name__)
settings = get_settings()
verify_api_key = create_api_key_dependency(api_key=settings.get("api_key"))




@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Make-Video Service starting...")

    for dir_path in [
        settings['audio_upload_dir'],
        settings['shorts_cache_dir'],
        '/tmp/make-video-temp',
        settings['output_dir'],
        settings['log_dir'],
    ]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    app.state.redis_store = get_redis_store()
    app.state.job_manager = get_job_manager()
    app.state.cache_manager = get_cache_manager()
    app.state.lock_manager = get_lock_manager()
    app.state.api_client = get_api_client()
    app.state._scheduler = None

    await app.state.redis_store.start_cleanup_task() if hasattr(app.state.redis_store, 'start_cleanup_task') else None

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        app.state._scheduler = AsyncIOScheduler()
        app.state._scheduler.add_job(
            cleanup_orphaned_videos_cron,
            trigger=IntervalTrigger(minutes=5),
            id='cleanup_orphaned_videos',
            name='Cleanup orphaned videos every 5 minutes',
            replace_existing=True,
        )
        app.state._scheduler.start()
    except Exception as e:
        logger.error("Failed to start APScheduler: %s", e, exc_info=True)

    logger.info("Make-Video Service ready!")
    yield

    logger.info("Make-Video Service shutting down...")
    if app.state._scheduler is not None:
        app.state._scheduler.shutdown(wait=False)
    await app.state.redis_store.stop_cleanup_task()
    await app.state.lock_manager.close()


cors_config = {
    "allow_origins": ["*"],
    "allow_credentials": False,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}


def setup_routers(app):
    app.include_router(api_router)


app = create_service_app(
    service_name="make-video-clip",
    title="Make-Video-Clip Service",
    description="Orquestra criação de vídeos a partir de clips de áudio + shorts + legendas",
    version="2.0.0",
    settings=settings,
    lifespan=lifespan,
    setup_routers=setup_routers,
    cors_config=cors_config,
    dependencies=[Depends(verify_api_key)],
)


async def cleanup_orphaned_videos_cron():
    try:
        from .pipeline import VideoPipeline
        pipeline = VideoPipeline()
        pipeline.cleanup_orphaned_files(max_age_minutes=10)
    except Exception as e:
        logger.error("CRON: Orphaned videos cleanup failed: %s", e, exc_info=True)


@app.get("/metrics")
async def prometheus_metrics(request: Request):
    try:
        import shutil
        try:
            temp_stat = shutil.disk_usage('/tmp/make-video-temp')
            disk_free_gb = temp_stat.free / (1024**3)
            disk_used_pct = (temp_stat.used / temp_stat.total) * 100
        except Exception:
            disk_free_gb = 0
            disk_used_pct = 100
        job_stats = request.app.state.job_manager.get_stats() if hasattr(request.app.state, 'job_manager') and request.app.state.job_manager else {}
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8005, reload=True, log_level="info")
