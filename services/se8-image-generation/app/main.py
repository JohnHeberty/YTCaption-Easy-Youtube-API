from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request

from common.fastapi_utils import create_service_app
from common.log_utils import get_logger

from app.core.config import get_settings
from app.api import (
    health_routes,
    generate_routes,
    generate_v2_routes,
    models_routes,
    tools_routes,
    file_routes,
)

logger = get_logger(__name__)
settings = get_settings()


async def verify_api_key(request: Request):
    if not settings.se8_api_key:
        return
    if request.url.path in ("/health", "/health/deep", "/ping", "/"):
        return
    key = request.headers.get("X-API-Key")
    if key != settings.se8_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", settings.app_name, settings.version)
    yield
    from app.services.image_service import fooocus_client
    await fooocus_client.close()
    logger.info("Shutting down Image Generation Service")


def setup_routers(app: FastAPI):
    app.include_router(health_routes.router)
    app.include_router(generate_routes.router, dependencies=[Depends(verify_api_key)])
    app.include_router(generate_v2_routes.router, dependencies=[Depends(verify_api_key)])
    app.include_router(models_routes.router, dependencies=[Depends(verify_api_key)])
    app.include_router(tools_routes.router, dependencies=[Depends(verify_api_key)])
    app.include_router(file_routes.router, dependencies=[Depends(verify_api_key)])


app = create_service_app(
    service_name="image-generation",
    title=settings.app_name,
    description="SDXL image generation service powered by Fooocus (full proxy)",
    version=settings.version,
    settings=settings,
    lifespan=lifespan,
    setup_routers=setup_routers,
)
