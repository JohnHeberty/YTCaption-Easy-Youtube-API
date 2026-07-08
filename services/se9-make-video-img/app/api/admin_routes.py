"""Admin routes for stats and cleanup."""
from __future__ import annotations

import os
import shutil
from typing import Any

from fastapi import APIRouter

from app.core.config import settings
from app.infrastructure.redis_store import get_video_job_store

router = APIRouter()
store = get_video_job_store()

# Statuses considered terminal (safe to clean up)
_TERMINAL_STATUSES = {"completed", "failed"}


@router.get("/admin/stats")
async def stats() -> dict[str, Any]:
    """System statistics."""
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

    return {
        "service": "make-video-img",
        "version": settings.app_version,
        "jobs": {
            "total": len(jobs),
            "by_status": status_counts,
        },
        "disk": disk_usage,
    }


@router.post("/admin/cleanup")
async def cleanup() -> dict[str, str]:
    """Cleanup failed jobs: remove output dirs AND Redis keys."""
    cleaned = 0

    for job in store.list_jobs():
        if job.get("status") == "failed":
            job_id = job.get("job_id", "")
            output_dir = os.path.join(settings.output_dir, job_id)
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)
            store.delete_job(job_id)
            cleaned += 1

    return {"detail": f"Cleaned up {cleaned} failed jobs (dirs + Redis keys)"}
