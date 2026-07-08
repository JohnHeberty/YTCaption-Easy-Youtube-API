"""Admin routes for stats and cleanup."""
from __future__ import annotations

import os
import shutil
from typing import Any

from fastapi import APIRouter

from app.core.config import settings
from app.api.schemas import AdminStatsResponse, AdminCleanupResponse, ErrorResponse
from app.infrastructure.redis_store import get_video_job_store

router = APIRouter(tags=["Admin"])
store = get_video_job_store()


@router.get(
    "/admin/stats",
    response_model=AdminStatsResponse,
    summary="System statistics",
    description=(
        "Returns system statistics including job counts by status and disk usage.\n\n"
        "Use this to monitor system health and capacity."
    ),
    responses={
        200: {"description": "System statistics"},
    },
)
async def stats() -> AdminStatsResponse:
    jobs = store.list_jobs()
    status_counts: dict[str, int] = {}
    for job in jobs:
        s = job.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    disk_usage: dict[str, dict[str, float]] = {}
    for d in [settings.temp_dir, settings.output_dir]:
        if os.path.exists(d):
            total, used, free = shutil.disk_usage(d)
            disk_usage[d] = {
                "total_gb": round(total / (1024**3), 1),
                "used_gb": round(used / (1024**3), 1),
                "free_gb": round(free / (1024**3), 1),
            }

    return AdminStatsResponse(
        service="make-video-img",
        version=settings.app_version,
        jobs={
            "total": len(jobs),
            "by_status": status_counts,
        },
        disk=disk_usage,
    )


@router.post(
    "/admin/cleanup",
    response_model=AdminCleanupResponse,
    summary="Cleanup failed jobs",
    description=(
        "Cleanup failed jobs: remove output directories AND Redis keys.\n\n"
        "**Only failed jobs** are cleaned up. Completed jobs are preserved."
    ),
    responses={
        200: {"description": "Cleanup result"},
    },
)
async def cleanup() -> AdminCleanupResponse:
    cleaned = 0

    for job in store.list_jobs():
        if job.get("status") == "failed":
            job_id = job.get("job_id", "")
            output_dir = os.path.join(settings.output_dir, job_id)
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)
            store.delete_job(job_id)
            cleaned += 1

    return AdminCleanupResponse(
        detail=f"Cleaned up {cleaned} failed jobs (dirs + Redis keys)"
    )
