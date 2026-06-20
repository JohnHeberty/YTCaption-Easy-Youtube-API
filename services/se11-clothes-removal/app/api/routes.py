"""Job routes for SE11 Clothes Removal."""
from __future__ import annotations

import os
import shutil
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.constants import JOB_ID_PREFIX
from app.core.models import (
    ClothesRemovalJob,
    ClothesRemovalJobStatus,
    CreateClothesRemovalRequest,
    CreateClothesRemovalResponse,
    JobStatusResponse,
)
from app.infrastructure.redis_store import ClothesRemovalJobStore
from app.worker import get_worker

router = APIRouter()
store = ClothesRemovalJobStore()


@router.get("/")
async def root() -> dict[str, Any]:
    """Service info endpoint."""
    return {
        "service": "clothes-removal",
        "version": "1.0.0",
        "endpoints": {
            "POST /jobs": "Create clothes removal job",
            "GET /jobs": "List all jobs",
            "GET /jobs/{job_id}": "Get job status",
            "DELETE /jobs/{job_id}": "Delete job",
            "GET /jobs/{job_id}/download": "Download result image",
            "GET /health": "Health check",
            "GET /admin/stats": "System statistics",
        },
    }


@router.post("/jobs", response_model=CreateClothesRemovalResponse)
async def create_job(request: CreateClothesRemovalRequest) -> CreateClothesRemovalResponse:
    """Create a new clothes removal job."""
    job_id = f"{JOB_ID_PREFIX}{uuid.uuid4().hex[:12]}"

    job = ClothesRemovalJob(
        job_id=job_id,
        request=request,
    )

    store.save_job(job_id, job.model_dump(mode="json"))

    worker = get_worker()
    worker.start()

    return CreateClothesRemovalResponse(
        job_id=job_id,
        status="queued",
        message="Clothes removal job started",
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Get the status of a clothes removal job."""
    job_data = store.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job_data["job_id"],
        status=job_data["status"],
        progress=job_data.get("progress", 0),
        stages=job_data.get("stages", {}),
        objects_detected=job_data.get("objects_detected"),
        created_at=job_data.get("created_at", ""),
        error=job_data.get("error"),
    )


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str) -> dict[str, str]:
    """Delete a clothes removal job and its files."""
    job_data = store.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    output_dir = os.path.join(settings.output_dir, job_id)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)

    result_path = job_data.get("result_path")
    if result_path and os.path.exists(result_path):
        os.remove(result_path)

    store.delete_job(job_id)
    return {"detail": f"Job {job_id} deleted"}


@router.get("/jobs")
async def list_jobs() -> dict[str, Any]:
    """List all clothes removal jobs."""
    jobs = store.list_jobs()
    return {
        "jobs": [
            {
                "job_id": j["job_id"],
                "status": j["status"],
                "progress": j.get("progress", 0),
                "objects_detected": j.get("objects_detected"),
                "created_at": j.get("created_at"),
            }
            for j in jobs
        ],
        "total": len(jobs),
    }
