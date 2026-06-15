from contextlib import asynccontextmanager

from fastapi import FastAPI

from common.fastapi_utils import create_service_app
from common.log_utils import get_logger

from app.core.config import get_settings
from app.api import jobs_routes, voices_routes, health_routes

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.version}")
    yield
    logger.info("Shutting down Audio Generation Service")


def setup_routers(app: FastAPI):
    app.include_router(jobs_routes.router)
    app.include_router(voices_routes.router)
    app.include_router(health_routes.router)


app = create_service_app(
    service_name="audio-generation",
    title=settings.app_name,
    description="TTS audio generation service for Brazilian Portuguese with voice cloning",
    version=settings.version,
    settings=settings,
    lifespan=lifespan,
    setup_routers=setup_routers,
)
