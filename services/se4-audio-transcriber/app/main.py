from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends
from common.log_utils import setup_structured_logging, get_logger
from common.fastapi_utils import create_service_app, create_api_key_dependency

from app.api import jobs_router, admin_router, model_router, health_router
from app.core.config import get_core

settings = get_core()
verify_api_key = create_api_key_dependency(api_key=settings.api_key)
setup_structured_logging(
    service_name="audio-transcriber",
    log_level=settings.log_level,
    log_dir=settings.log_dir,
    json_format=True,
)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: Any) -> Any:
    from app.infrastructure.dependencies import job_store, processor

    try:
        store = job_store()
        await store.start_cleanup_task()
        logger.info("Audio Transcription Service started")
    except Exception as e:
        logger.error("Error during startup: %s", e)
        raise

    yield

    try:
        store = job_store()
        await store.stop_cleanup_task()
        logger.info("Audio Transcription Service stopped")
    except Exception as e:
        logger.error("Error during shutdown: %s", e)


def setup_routers(app: Any) -> None:
    app.include_router(jobs_router)
    app.include_router(admin_router)
    app.include_router(model_router)
    app.include_router(health_router)


app = create_service_app(
    service_name="audio-transcriber",
    title="Audio Transcription Service",
    description="Microserviço para transcrição de áudio com cache de 24h",
    version="2.0.0",
    settings=settings,
    lifespan=lifespan,
    setup_routers=setup_routers,
    body_size_mb=settings.max_file_size_mb,
    dependencies=[Depends(verify_api_key)],
)


from app.api.schemas import RootResponse


@app.get(
    "/",
    summary="Service info",
    description="Retorna a visão geral do serviço e o catálogo resumido dos endpoints públicos de transcrição.",
    response_model=RootResponse,
)
async def root() -> dict[str, Any]:
    return {
        "service": "Audio Transcription Service",
        "version": "2.0.0",
        "status": "running",
        "description": "Microserviço para transcrição de áudio com cache de 24h",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "jobs": {
                "create": "POST /jobs",
                "get": "GET /jobs/{job_id}",
                "list": "GET /jobs",
                "download": "GET /jobs/{job_id}/download",
                "text": "GET /jobs/{job_id}/text",
                "transcription": "GET /jobs/{job_id}/transcription",
                "delete": "DELETE /jobs/{job_id}",
                "orphaned": "GET /jobs/orphaned",
                "orphaned_cleanup": "POST /jobs/orphaned/cleanup"
            },
            "metadata": {
                "languages": "GET /languages",
                "engines": "GET /engines"
            },
            "admin": {
                "stats": "GET /admin/stats",
                "queue": "GET /admin/queue",
                "cleanup": "POST /admin/cleanup"
            },
            "model": {
                "status": "GET /model/status",
                "load": "POST /model/load",
                "unload": "POST /model/unload"
            }
        }
    }
