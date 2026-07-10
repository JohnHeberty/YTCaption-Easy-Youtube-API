from __future__ import annotations

"""Admin routes for SE7 Audio Generation."""

from fastapi import APIRouter, Depends

from app.api.schemas import AdminCleanupResponse, AdminStatsResponse, AdminJobStats
from app.infrastructure.dependencies import job_store
from app.domain.interfaces import IJobStore

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats", response_model=AdminStatsResponse)
async def stats(store: IJobStore = Depends(job_store)) -> AdminStatsResponse:
    """System statistics."""
    jobs = store.list_jobs(limit=100)
    status_counts: dict[str, int] = {}
    for job in jobs:
        s = job.status.value if hasattr(job.status, "value") else str(job.status)
        status_counts[s] = status_counts.get(s, 0) + 1

    return AdminStatsResponse(
        service="audio-generation",
        jobs=AdminJobStats(
            total=len(jobs),
            by_status=status_counts,
        ),
    )


@router.post("/cleanup", response_model=AdminCleanupResponse)
async def cleanup(store: IJobStore = Depends(job_store)) -> AdminCleanupResponse:
    """Cleanup completed and failed jobs."""
    jobs = store.list_jobs(limit=100)
    cleaned = 0
    for job in jobs:
        status = job.status.value if hasattr(job.status, "value") else str(job.status)
        if status in ("completed", "failed"):
            store.delete_job(job.id)
            cleaned += 1

    return AdminCleanupResponse(
        jobs_removed=cleaned,
        message=f"Cleaned up {cleaned} completed/failed jobs",
    )
