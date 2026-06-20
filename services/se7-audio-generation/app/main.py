from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Depends
from starlette.applications import Starlette

from common.fastapi_utils import create_service_app, create_api_key_dependency
from common.log_utils import setup_structured_logging, get_logger

from app.core.config import get_settings
from app.api import jobs_routes, voices_routes, health_routes, admin_routes

settings = get_settings()
setup_structured_logging(service_name="audio-generation", log_level=settings.log_level, log_dir=settings.log_dir)
logger = get_logger(__name__)
verify_api_key = create_api_key_dependency(api_key=settings.api_key)


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    try:
        from app.infrastructure.dependencies import get_voice_manager
        from app.services.voice_seeder import seed_builtin_voices
        mgr = get_voice_manager()
        seed_builtin_voices(mgr, settings.voices_dir)
    except Exception as e:
        logger.warning(f"Voice seeding failed (non-fatal): {e}")
    yield
    logger.info("Shutting down Audio Generation Service")


def setup_routers(app: FastAPI) -> None:
    app.include_router(jobs_routes.router)
    app.include_router(voices_routes.router)
    app.include_router(health_routes.router)
    app.include_router(admin_routes.router)


app = create_service_app(
    service_name="audio-generation",
    title=settings.app_name,
    description="TTS audio generation service for Brazilian Portuguese with voice cloning",
    version=settings.app_version,
    settings=settings,
    lifespan=lifespan,
    setup_routers=setup_routers,
    dependencies=[Depends(verify_api_key)],
)
