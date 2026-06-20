from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from common.health_utils import ServiceHealthChecker
from common.datetime_utils import now_brazil

from app.core.config import get_settings
from app.domain.interfaces import IModelManager, IJobStore
from app.infrastructure.dependencies import model_manager, job_store

router = APIRouter(tags=["Health"])


@router.get("/")
async def root() -> dict[str, str]:
    settings = get_settings()
    return {"service": settings.app_name, "version": settings.app_version, "status": "running"}


def _check_redis(store: IJobStore) -> dict[str, str]:
    try:
        store.list_jobs(1)
        return {"name": "redis", "status": "ok"}
    except Exception as e:
        return {"name": "redis", "status": "error", "detail": str(e)}


@router.get("/health")
async def health(
    model_mgr: IModelManager = Depends(model_manager),
    store: IJobStore = Depends(job_store),
) -> dict[str, Any]:
    settings = get_settings()
    checker = ServiceHealthChecker("audio-generation", version=settings.app_version)

    checker.add_check("redis", lambda: _check_redis(store))

    status = model_mgr.get_status()
    model_status = "ok" if status.get("loaded") else "degraded"
    model_detail = (
        f"Model {'loaded' if status.get('loaded') else 'not loaded'}"
        f" | Device: {status.get('device', 'unknown')}"
    )
    checker.add_check("model", lambda: {
        "name": "model",
        "status": model_status,
        "detail": model_detail,
    })

    checker.add_check(
        "disk",
        lambda: ServiceHealthChecker.check_disk(settings.output_dir, min_free_gb=0.5),
    )

    result = await checker.check_all()
    result["timestamp"] = now_brazil().isoformat()
    return result
