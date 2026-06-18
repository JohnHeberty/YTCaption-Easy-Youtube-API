"""API routes for video job management."""
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.core.constants import JOB_ID_PREFIX
from app.core.models import (
    CreateVideoRequest,
    CreateVideoResponse,
    JobStatusResponse,
    VideoJob,
    VideoJobStatus,
)
from app.infrastructure.redis_store import VideoJobStore
from app.worker import get_worker

router = APIRouter()
store = VideoJobStore()


@router.post("/jobs", response_model=CreateVideoResponse)
async def create_job(request: CreateVideoRequest):
    """Create a new video generation job."""
    job_id = f"{JOB_ID_PREFIX}{uuid.uuid4().hex[:12]}"

    job = VideoJob(
        job_id=job_id,
        post_id=request.post_id,
        request=request,
    )

    store.save_job(job_id, job.model_dump(mode="json"))

    worker = get_worker()
    worker.start()

    return CreateVideoResponse(
        job_id=job_id,
        status="queued",
        post_id=request.post_id,
        estimated_seconds=request.estimated_seconds,
        scenes_count=len(request.scene_suggestions),
        message="Video generation started",
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get the status of a video job."""
    job_data = store.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job_data["job_id"],
        status=job_data["status"],
        progress=job_data.get("progress", 0),
        stages=job_data.get("stages", {}),
        created_at=job_data.get("created_at", ""),
        error=job_data.get("error"),
    )


@router.get("/jobs")
async def list_jobs():
    """List all video jobs."""
    jobs = store.list_jobs()
    return {
        "jobs": [
            {
                "job_id": j["job_id"],
                "status": j["status"],
                "progress": j.get("progress", 0),
                "post_id": j.get("post_id"),
                "created_at": j.get("created_at"),
            }
            for j in jobs
        ],
        "total": len(jobs),
    }
