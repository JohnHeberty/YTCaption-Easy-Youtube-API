"""API routes for video job management."""
from __future__ import annotations

import os
import shutil
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Depends

from app.core.config import settings
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


@router.get("/")
async def root() -> dict[str, Any]:
    """Service info endpoint."""
    return {
        "service": "make-video-img",
        "version": settings.app_version,
        "endpoints": {
            "POST /jobs": "Create video generation job",
            "GET /jobs": "List all jobs",
            "GET /jobs/{job_id}": "Get job status",
            "DELETE /jobs/{job_id}": "Delete job",
            "GET /download/{job_id}": "Download completed video",
            "GET /health": "Health check",
            "GET /admin/stats": "System statistics",
            "POST /admin/cleanup": "Cleanup temp files and failed jobs",
        },
    }


@router.post("/jobs", response_model=CreateVideoResponse)
async def create_job(request: CreateVideoRequest) -> CreateVideoResponse:
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
async def get_job_status(job_id: str) -> JobStatusResponse:
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


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str) -> dict[str, str]:
    """Delete a video job and its output directory."""
    job_data = store.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    output_dir = os.path.join(settings.output_dir, job_id)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)

    store.delete_job(job_id)
    return {"detail": f"Job {job_id} deleted"}


@router.get("/jobs")
async def list_jobs() -> dict[str, Any]:
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
