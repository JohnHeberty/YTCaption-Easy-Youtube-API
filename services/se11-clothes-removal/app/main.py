"""FastAPI application for SE11 Clothes Removal."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.openapi.utils import get_openapi

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
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    from app.worker import get_worker

    worker = get_worker()
    worker.start()
    yield
    worker.stop()
    logger.info("Shutting down %s", settings.app_name)


def setup_routers(app: FastAPI) -> None:
    app.include_router(health_router)
    app.include_router(jobs_router)
    app.include_router(download_router)
    app.include_router(admin_router)


app = create_service_app(
    service_name="clothes-removal",
    title="SE11 — Clothes Removal API",
    description=(
        "Professional clothes removal service powered by SE10 (GroundingDINO/Florence-2) "
        "object detection and SE8 (Fooocus/JuggernautXL) inpainting.\n\n"
        "## Features\n"
        "- **Clothes removal** — detects and removes clothing via AI inpainting\n"
        "- **NSFW pipeline** — production pipeline with retry loop, pose validation, and best selection\n"
        "- **Person mode** — full torso removal with head protection\n"
        "- **Debug grid** — visual pipeline step-by-step output\n\n"
        "## Modes\n"
        "| Mode | Description |\n|------|-------------|\n"
        "| `clothes` | Default — removes detected clothing |\n"
        "| `person` | Removes entire torso (head preserved) |\n"
        "| `nsfw` | Production NSFW pipeline (body_mask + retry + pose validation) |\n"
        "| `nsfw_test` | Alias for nsfw |\n\n"
        "## Upstream Services\n"
        "- **SE10** (port 8010) — Object detection (GroundingDINO + Florence-2)\n"
        "- **SE8** (port 8008) — Image inpainting (Fooocus + JuggernautXL + NSFW LoRAs)"
    ),
    version=settings.app_version,
    settings=settings,
    lifespan=lifespan,
    setup_routers=setup_routers,
    dependencies=[Depends(verify_api_key)],
)


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["info"]["contact"] = {
        "name": "SE11 Clothes Removal",
        "description": "Pipeline: SE10 detection → SE8 inpainting → pose validation",
    }
    schema["info"]["license"] = {"name": "Internal"}
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]
