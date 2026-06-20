"""Health and utility routes for SE8 Image Engine."""

from __future__ import annotations
from common.log_utils import get_logger

from typing import Optional

from fastapi import APIRouter, Response

from app.core.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(tags=["Health"])


@router.get(
    "/",
    include_in_schema=False,
)
def home():
    """Home page."""
    return Response(
        content=(
            "<h2>SE8 Image Engine</h2>"
            "<ul>"
            "<li><a href=\"/docs\">Swagger UI (API docs)</a></li>"
            "<li><a href=\"/redoc\">ReDoc</a></li>"
            "</ul>"
        ),
        media_type="text/html",
    )


@router.get("/health", tags=["Health"])
def health():
    """Basic health check."""
    try:
        from app.services.worker import worker_queue

        queue_size = len(worker_queue.queue) if worker_queue else 0
        return {
            "status": "healthy",
            "service": "se8-image-generation",
            "version": settings.version,
            "queue_size": queue_size,
        }
    except Exception as e:
        return {
            "status": "degraded",
            "service": "se8-image-generation",
            "error": str(e),
        }


@router.get("/health/deep", tags=["Health"])
def health_deep():
    """Deep health check with component status."""
    checks = {}
    try:
        from app.services.worker import worker_queue

        checks["worker_queue"] = {
            "status": "ok",
            "queue_size": len(worker_queue.queue) if worker_queue else 0,
        }
    except Exception as e:
        checks["worker_queue"] = {"status": "error", "error": str(e)}

    try:
        from app.services.model_manager import get_model_manager

        mm = get_model_manager()
        checks["gpu"] = {
            "status": "ok",
            "device": mm.device_name,
            "vram_total_mb": mm.total_vram_mb,
        }
    except Exception as e:
        checks["gpu"] = {"status": "unavailable", "error": str(e)}

    return {
        "status": "healthy",
        "service": "se8-image-generation",
        "version": settings.version,
        "checks": checks,
    }


@router.get("/ping", tags=["Health"])
async def ping():
    """Ping — returns pong."""
    return "pong"
