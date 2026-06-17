from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request

from common.fastapi_utils import create_service_app
from common.log_utils import get_logger

from app.core.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


async def verify_api_key(request: Request):
    if not settings.se9_api_key:
        return
    if request.url.path in ("/health", "/health/deep", "/ping", "/"):
        return
    key = request.headers.get("X-API-Key")
    if key != settings.se9_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", settings.app_name, settings.version)
    import threading
    from app.services.task_queue import TaskQueue
    import app.services.worker as worker_mod

    if worker_mod.worker_queue is None:
        worker_mod.worker_queue = TaskQueue(queue_size=settings.max_queue_size)

    _worker_thread = threading.Thread(
        target=worker_mod.task_schedule_loop, daemon=True, name="se9-worker"
    )
    _worker_thread.start()
    logger.info("Worker task loop started in background thread")

    yield

    logger.info("Shutting down %s", settings.app_name)


def setup_routers(app: FastAPI):
    from app.api import (
        file_routes,
        generate_routes,
        generate_v2_routes,
        health_routes,
        models_routes,
        query_routes,
        tools_routes,
    )

    app.include_router(health_routes.router)
    app.include_router(query_routes.router, dependencies=[Depends(verify_api_key)])
    app.include_router(
        generate_routes.router, dependencies=[Depends(verify_api_key)]
    )
    app.include_router(
        generate_v2_routes.router, dependencies=[Depends(verify_api_key)]
    )
    app.include_router(
        models_routes.router, dependencies=[Depends(verify_api_key)]
    )
    app.include_router(tools_routes.router, dependencies=[Depends(verify_api_key)])
    app.include_router(file_routes.router, dependencies=[Depends(verify_api_key)])


app = create_service_app(
    service_name="image-engine",
    title=settings.app_name,
    description="SE9 Image Engine — Full FOOOCUS rewrite (SDXL, lazy/eager GPU, Celery)",
    version=settings.version,
    settings=settings,
    lifespan=lifespan,
    setup_routers=setup_routers,
)
