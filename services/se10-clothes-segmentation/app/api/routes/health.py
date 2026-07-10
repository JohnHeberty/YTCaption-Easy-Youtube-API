"""Health check routes for SE10 Clothes Segmentation."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter

from app.core.config import get_settings
from app.state import get_segmentor
from app.domain.models import HealthResponse, DeepHealthResponse, PingResponse

router = APIRouter(tags=["Health"])

_server_start_time = time.time()


def _get_uptime() -> float:
    return round(time.time() - _server_start_time, 1)


@router.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    seg = get_segmentor()
    return HealthResponse(
        status="ok",
        model_loaded=seg is not None,
        device=seg.device if seg else "unknown",
        version=get_settings().version,
    )


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    seg = get_segmentor()
    return HealthResponse(
        status="ok",
        model_loaded=seg is not None,
        device=seg.device if seg else "unknown",
        version=get_settings().version,
    )


@router.get("/health/deep", response_model=DeepHealthResponse)
async def health_deep() -> DeepHealthResponse:
    settings = get_settings()
    seg = get_segmentor()

    checkpoint_status: dict[str, dict[str, object]] = {}
    for name in ["yolo11m-seg.pt"]:
        fpath = Path(name)
        if fpath.exists():
            checkpoint_status[name] = {"exists": True, "size_mb": round(fpath.stat().st_size / 1024 / 1024, 1)}
        else:
            checkpoint_status[name] = {"exists": False, "size_mb": 0}

    return DeepHealthResponse(
        status="ok" if seg else "degraded",
        model_loaded=seg is not None,
        device=seg.device if seg else "unknown",
        version=settings.version,
        checkpoints=checkpoint_status,
        uptime_s=_get_uptime(),
    )


@router.get("/ping", response_model=PingResponse)
async def ping() -> PingResponse:
    return PingResponse(pong=True)
