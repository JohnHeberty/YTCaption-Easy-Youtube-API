"""Health check routes using shared ServiceHealthChecker."""
from __future__ import annotations

from typing import Any

import httpx

from fastapi import APIRouter

from app.core.config import settings
from app.api.schemas import HealthResponse, PingResponse
from common.health_utils import ServiceHealthChecker

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description=(
        "Check service health including SE7, SE8, disk, and FFmpeg.\n\n"
        "Returns `status: ok` if all checks pass, or `status: degraded` if any fail.\n\n"
        "**Use this** as a liveness probe for container orchestration."
    ),
    responses={
        200: {"description": "Health status"},
    },
)
async def health_check() -> dict[str, Any]:
    checker = ServiceHealthChecker("make-video-img", version=settings.app_version)

    async def check_se7() -> dict[str, str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{settings.se7_url}/health")
                if resp.status_code == 200:
                    return {"status": "ok"}
                return {"status": "error", "message": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def check_se8() -> dict[str, str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{settings.se8_url}/health")
                if resp.status_code == 200:
                    return {"status": "ok"}
                return {"status": "error", "message": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    checker.add_check("se7", check_se7)
    checker.add_check("se8", check_se8)
    checker.add_check("disk", lambda: ServiceHealthChecker.check_disk("/tmp"))
    checker.add_check("ffmpeg", lambda: ServiceHealthChecker.check_ffmpeg())

    return await checker.check_all()


@router.get(
    "/ping",
    response_model=PingResponse,
    summary="Ping",
    description="Simple connectivity test. Returns `{\"pong\": true}`.",
    responses={
        200: {"description": "Pong response"},
    },
)
async def ping() -> PingResponse:
    return PingResponse(pong=True)
