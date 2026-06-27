"""Admin routes for SE11 Clothes Removal."""
from __future__ import annotations

import os
import shutil

from fastapi import APIRouter

from app.api.schemas import AdminCleanupResponse, AdminStatsResponse
from app.core.config import settings
from app.infrastructure.redis_store import ClothesRemovalJobStore

router = APIRouter(prefix="/admin", tags=["Admin"])
store = ClothesRemovalJobStore()


@router.get(
    "/stats",
    response_model=AdminStatsResponse,
    summary="System statistics",
    description="Returns job counts by status and disk usage.",
)
async def stats() -> AdminStatsResponse:
    jobs = store.list_jobs()
    status_counts: dict[str, int] = {}
    for job in jobs:
        s = job.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    output_dir = settings.output_dir
    total_files = 0
    total_size_mb = 0.0
    if os.path.exists(output_dir):
        for root, _dirs, files in os.walk(output_dir):
            for f in files:
                fp = os.path.join(root, f)
                total_files += 1
                total_size_mb += os.path.getsize(fp) / (1024 * 1024)

    return AdminStatsResponse(
        jobs={
            "total": len(jobs),
            "by_status": status_counts,
        },
        storage={
            "output_dir": output_dir,
            "total_files": total_files,
            "total_size_mb": round(total_size_mb, 2),
        },
    )


@router.post(
    "/cleanup",
    response_model=AdminCleanupResponse,
    summary="Cleanup jobs",
    description="Remove completed/failed jobs and their output files.",
)
async def cleanup() -> AdminCleanupResponse:
    jobs = store.list_jobs()
    cleaned = 0
    for job in jobs:
        if job.get("status") in ("failed", "completed"):
            output_dir = os.path.join(settings.output_dir, job["job_id"])
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)
            store.delete_job(job["job_id"])
            cleaned += 1

    return AdminCleanupResponse(cleaned=cleaned)
