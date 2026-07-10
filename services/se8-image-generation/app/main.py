from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse

from common.fastapi_utils import create_service_app, create_api_key_dependency
from common.log_utils import get_logger

from app.core.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

verify_api_key = create_api_key_dependency(api_key=settings.se8_api_key)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting %s v%s", settings.app_name, settings.version)
    import threading
    from app.services.task_queue import TaskQueue
    import app.services.worker as worker_mod

    if worker_mod.worker_queue is None:
        redis_store = None
        try:
            from common.redis_utils.resilient_store import ResilientRedisStore
            redis_store = ResilientRedisStore(
                redis_url=settings.redis_url,
                max_connections=10,
                circuit_breaker_enabled=True,
            )
            logger.info("Redis-backed history enabled")
        except Exception as e:
            logger.warning("Redis unavailable, history will be in-memory only: %s", e)

        worker_mod.worker_queue = TaskQueue(
            queue_size=settings.max_queue_size,
            redis_store=redis_store,
        )

    _worker_thread = threading.Thread(
        target=worker_mod.task_schedule_loop, daemon=True, name="se8-worker"
    )
    _worker_thread.start()
    logger.info("Worker task loop started in background thread")

    yield

    logger.info("Shutting down %s", settings.app_name)


def setup_routers(app: FastAPI) -> None:
    from app.api import (
        admin_routes,
        face_routes,
        file_routes,
        generate_routes,
        generate_v2_routes,
        health_routes,
        models_routes,
        query_routes,
        tools_routes,
    )

    app.include_router(health_routes.router)
    app.include_router(admin_routes.router, dependencies=[Depends(verify_api_key)])
    app.include_router(query_routes.router, dependencies=[Depends(verify_api_key)])
    app.include_router(
        generate_routes.router, dependencies=[Depends(verify_api_key)]
    )
    app.include_router(
        generate_v2_routes.router, dependencies=[Depends(verify_api_key)]
    )
    app.include_router(
        face_routes.router, dependencies=[Depends(verify_api_key)]
    )
    app.include_router(
        models_routes.router, dependencies=[Depends(verify_api_key)]
    )
    app.include_router(tools_routes.router, dependencies=[Depends(verify_api_key)])
    app.include_router(file_routes.router, dependencies=[Depends(verify_api_key)])


app = create_service_app(
    service_name="image-engine",
    title=settings.app_name,
    description="SE8 Image Engine — SDXL inference engine with lazy/eager GPU and in-memory worker",
    version=settings.version,
    settings=settings,
    lifespan=lifespan,
    setup_routers=setup_routers,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler — returns consistent ErrorResponse shape."""
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "error_code": "INTERNAL_ERROR"},
    )


@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Validation error handler — returns consistent ErrorResponse shape."""
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "error_code": "VALIDATION_ERROR"},
    )
