"""Admin routes for stats and cleanup."""
import os
import shutil

from fastapi import APIRouter

from app.core.config import settings
from app.infrastructure.redis_store import VideoJobStore

router = APIRouter()
store = VideoJobStore()


@router.get("/admin/stats")
async def stats():
    """System statistics."""
    jobs = store.list_jobs()
    status_counts = {}
    for job in jobs:
        s = job.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    disk_usage = {}
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
async def cleanup():
    """Cleanup old temp files and failed jobs."""
    cleaned = 0

    for job in store.list_jobs():
        if job.get("status") in ("failed", "completed"):
            temp_dir = os.path.join(settings.temp_dir, f"rbg_{job['job_id']}")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                cleaned += 1

    return {"detail": f"Cleaned up {cleaned} temp directories"}
