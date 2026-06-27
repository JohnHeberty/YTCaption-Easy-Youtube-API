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
        "## Authentication\n"
        "All endpoints require an API key in the `X-API-Key` header.\n"
        "Click the **Authorize** button above and enter your key.\n\n"
        "## Features\n"
        "- **Clothes removal** — detects and removes clothing via AI inpainting\n"
        "- **NSFW pipeline** — production pipeline with retry loop, pose validation, and best selection\n"
        "- **Person mode** — full torso removal with head protection\n"
        "- **Debug grid** — visual pipeline step-by-step output\n\n"
        "## Quick Start\n"
        "1. Click **Authorize** → enter your API key\n"
        "2. Go to `POST /jobs` → click **Try it out**\n"
        "3. Upload an AI-generated image (PNG/JPEG/WebP)\n"
        "4. Click **Execute** → get `job_id`\n"
        "5. Poll `GET /jobs/{job_id}` until `status: completed`\n"
        "6. Download result via `GET /jobs/{job_id}/download`\n\n"
        "## Modes\n"
        "| Mode | Description |\n|------|-------------|\n"
        "| `nsfw` ⭐ | Production pipeline (retry + pose validation) — **recommended** |\n"
        "| `clothes` | Default — removes detected clothing |\n"
        "| `person` | Removes entire torso (head preserved) |\n"
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


OPENAPI_TAGS = [
    {
        "name": "Jobs",
        "description": (
            "Create, list, poll, and delete clothes removal jobs.\n\n"
            "Use `POST /jobs` to start a job, then `GET /jobs/{job_id}` to poll progress.\n"
            "Job status transitions: `queued` → `detecting` → `inpainting` → `completed` | `failed`."
        ),
    },
    {
        "name": "Health",
        "description": (
            "Health checks and service metadata.\n\n"
            "- `GET /health` — Liveness probe (always 200 if service is up)\n"
            "- `GET /health/deep` — Checks upstream connectivity (SE10, SE8)\n"
            "- `GET /ping` — Simple connectivity test\n"
            "- `GET /` — Service info and endpoint catalog"
        ),
    },
    {
        "name": "Admin",
        "description": (
            "System administration endpoints.\n\n"
            "- `GET /admin/stats` — Job counts by status and disk usage\n"
            "- `POST /admin/cleanup` — Remove completed/failed jobs and their output files"
        ),
    },
]


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=OPENAPI_TAGS,
    )
    schema["info"]["contact"] = {
        "name": "SE11 Clothes Removal",
        "description": "Pipeline: SE10 detection → SE8 inpainting → pose validation",
    }
    schema["info"]["license"] = {"name": "Internal"}

    # Add API key authentication to Swagger UI ("Authorize" button)
    schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for authentication. Enter your key and click Authorize.",
        }
    }
    schema["security"] = [{"ApiKeyAuth": []}]

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]
