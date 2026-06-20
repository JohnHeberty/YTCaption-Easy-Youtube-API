"""Health routes for SE11 Clothes Removal."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Basic health check."""
    return {"status": "ok", "service": "clothes-removal", "version": "1.0.0"}


@router.get("/health/deep")
async def health_deep() -> dict[str, Any]:
    """Deep health check with upstream status."""
    from app.infrastructure.http_client import SE10Client, SE8Client

    status: dict[str, str] = {"se11": "ok", "se10": "unknown", "se8": "unknown"}

    try:
        se10 = SE10Client()
        await se10.health()
        status["se10"] = "ok"
        await se10.close()
    except Exception:
        status["se10"] = "unreachable"

    try:
        se8 = SE8Client()
        await se8.health()
        status["se8"] = "ok"
        await se8.close()
    except Exception:
        status["se8"] = "unreachable"

    all_ok = all(v == "ok" for v in status.values())
    return {"status": "ok" if all_ok else "degraded", "services": status}


@router.get("/ping")
async def ping() -> dict[str, bool]:
    """Simple ping."""
    return {"pong": True}
