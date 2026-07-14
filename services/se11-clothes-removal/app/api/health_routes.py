"""Health routes for SE11 Clothes Removal."""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter

from app.api.schemas import (
    DeepHealthCheck,
    DeepHealthResponse,
    HealthResponse,
    PingResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description=(
        "Basic **liveness probe**.\n\n"
        "Returns `200 OK` if the service process is running.\n"
        "Use this for load balancers and container health checks.\n\n"
        "Does NOT check upstream services — use `GET /health/deep` for that."
    ),
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/health/deep",
    response_model=DeepHealthResponse,
    summary="Deep health check",
    description=(
        "Checks connectivity to **all upstream services** (SE10, SE8).\n\n"
        "Returns per-service status and latency. Overall status:\n"
        "- `ok` — all services reachable\n"
        "- `degraded` — at least one service unreachable\n\n"
        "**Use this** to verify the full pipeline is operational before submitting jobs."
    ),
    responses={
        200: {"description": "Health status with upstream details"},
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
    except Exception as e:
        logger.debug("SE10 health check failed: %s", e)
        checks["se10"] = DeepHealthCheck(status="unreachable").model_dump()

    # SE8 check
    t0 = time.time()
    try:
        se8 = SE8Client()
        await se8.health()
        latency = round((time.time() - t0) * 1000, 1)
        await se8.close()
        checks["se8"] = DeepHealthCheck(status="ok", latency_ms=latency).model_dump()
    except Exception as e:
        logger.debug("SE8 health check failed: %s", e)
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
