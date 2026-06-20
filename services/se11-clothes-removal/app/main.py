"""FastAPI application for SE11 Clothes Removal."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from common.fastapi_utils import create_api_key_dependency, create_service_app
from common.log_utils import get_logger, setup_structured_logging

from app.api.admin_routes import router as admin_router
from app.api.download_routes import router as download_router
from app.api.health_routes import router as health_router
from app.api.routes import router as jobs_router
from app.core.config import get_settings

settings = get_settings()
setup_structured_logging(
    service_name="clothes-removal",
    log_level=settings.log_level,
    log_dir=settings.log_dir,
)
logger = get_logger(__name__)
verify_api_key = create_api_key_dependency(api_key=settings.api_key)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    from app.worker import get_worker

    worker = get_worker()
    worker.start()
    yield
    worker.stop()
    logger.info("Shutting down %s", settings.app_name)


def setup_routers(app: FastAPI):
    app.include_router(health_router)
    app.include_router(jobs_router)
    app.include_router(download_router)
    app.include_router(admin_router)


app = create_service_app(
    service_name="clothes-removal",
    title=settings.app_name,
    description="Clothes removal service — detects clothing via SE10, removes via SE8 inpainting",
    version=settings.app_version,
    settings=settings,
    lifespan=lifespan,
    setup_routers=setup_routers,
    dependencies=[Depends(verify_api_key)],
)
