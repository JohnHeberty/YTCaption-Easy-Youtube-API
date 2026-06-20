"""Health check routes using shared ServiceHealthChecker."""
from __future__ import annotations

from typing import Any

import httpx

from fastapi import APIRouter

from app.core.config import settings
from common.health_utils import ServiceHealthChecker

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Check service health including SE7, SE8, disk, and ffmpeg."""
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


@router.get("/ping")
async def ping() -> dict[str, bool]:
    """Simple ping endpoint."""
    return {"pong": True}
