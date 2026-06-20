"""SE10 Clothes Segmentation — FastAPI application."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends

from common.fastapi_utils import create_service_app, create_api_key_dependency
from common.log_utils import get_logger

from app.core.config import get_settings
from app.state import set_segmentor, clear_segmentor

logger = get_logger(__name__)
settings = get_settings()

verify_api_key = create_api_key_dependency(api_key=settings.se10_api_key)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting %s v%s", settings.app_name, settings.version)

    import time
    from pathlib import Path

    from app.services.segmentor import ClothesSegmentor

    checkpoints_dir = Path(settings.checkpoint_dir).resolve()
    gd_ckpt = checkpoints_dir / "groundingdino_swint_ogc.pth"
    sam2_ckpt = checkpoints_dir / "sam2_hiera_tiny.pt"

    if not gd_ckpt.exists() or not sam2_ckpt.exists():
        logger.warning(
            "Checkpoints not found in %s — running in degraded mode (segmentation disabled)",
            checkpoints_dir,
        )
    else:
        try:
            t0 = time.time()
            seg = ClothesSegmentor(settings=settings)
            set_segmentor(seg)
            logger.info("Models loaded in %.1fs", time.time() - t0)
        except Exception:
            logger.exception("Failed to load models — running in degraded mode")

    yield

    logger.info("Shutting down %s", settings.app_name)
    clear_segmentor()


def setup_routers(app: FastAPI) -> None:
    from app.api.routes import health, segment, jobs

    app.include_router(health.router)
    app.include_router(segment.router, dependencies=[Depends(verify_api_key)])
    app.include_router(jobs.router, dependencies=[Depends(verify_api_key)])


app = create_service_app(
    service_name="clothes-segmentation",
    title=settings.app_name,
    description="SE10 Clothes Segmentation — GroundingDINO + SAM2 clothing detection and segmentation",
    version=settings.version,
    settings=settings,
    lifespan=lifespan,
    setup_routers=setup_routers,
    cors_options={
        "allow_origins": ["*"],
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    },
)
