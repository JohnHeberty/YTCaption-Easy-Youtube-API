"""Health routes for SE11 Clothes Removal."""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter

from app.api.schemas import (
    DeepHealthCheck,
    DeepHealthResponse,
    ErrorResponse,
    HealthResponse,
    PingResponse,
)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Basic liveness check.",
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/health/deep",
    response_model=DeepHealthResponse,
    summary="Deep health check",
    description="Verifies connectivity to upstream services (SE10, SE8).",
    responses={
        200: {"description": "Health status"},
    },
)
async def health_deep() -> DeepHealthResponse:
    from app.infrastructure.http_client import SE10Client, SE8Client

    checks: dict[str, Any] = {}

    # SE10 check
    t0 = time.time()
    try:
        se10 = SE10Client()
        await se10.health()
        latency = round((time.time() - t0) * 1000, 1)
        await se10.close()
        checks["se10"] = DeepHealthCheck(status="ok", latency_ms=latency).model_dump()
    except Exception:
        checks["se10"] = DeepHealthCheck(status="unreachable").model_dump()

    # SE8 check
    t0 = time.time()
    try:
        se8 = SE8Client()
        await se8.health()
        latency = round((time.time() - t0) * 1000, 1)
        await se8.close()
        checks["se8"] = DeepHealthCheck(status="ok", latency_ms=latency).model_dump()
    except Exception:
        checks["se8"] = DeepHealthCheck(status="unreachable").model_dump()

    all_ok = all(c.get("status") == "ok" for c in checks.values())
    return DeepHealthResponse(
        status="ok" if all_ok else "degraded",
        checks=checks,
    )


@router.get(
    "/ping",
    response_model=PingResponse,
    summary="Ping",
    description="Simple connectivity test.",
)
async def ping() -> PingResponse:
    return PingResponse()
