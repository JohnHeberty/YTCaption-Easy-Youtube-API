"""Job routes for SE11 Clothes Removal."""
from __future__ import annotations

import os
import shutil
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.config import settings
from app.core.constants import JOB_ID_PREFIX
from app.core.models import ClothesRemovalJob
from app.api.schemas import (
    CreateClothesRemovalRequest,
    CreateClothesRemovalResponse,
    DeleteJobResponse,
    ErrorResponse,
    JobListItem,
    JobStatusResponse,
    ListJobsResponse,
)
from app.infrastructure.redis_store import ClothesRemovalJobStore
from app.worker import get_worker

router = APIRouter(tags=["Jobs"])
store = ClothesRemovalJobStore()


# Service info
class ServiceInfoResponse(BaseModel):
    service: str = "clothes-removal"
    version: str = "1.0.0"
    endpoints: dict[str, str]


@router.get(
    "/",
    response_model=ServiceInfoResponse,
    summary="Service info",
    description="Returns service name, version, and available endpoints.",
)
async def root() -> ServiceInfoResponse:
    return ServiceInfoResponse(
        endpoints={
            "POST /jobs": "Create clothes removal job",
            "GET /jobs": "List all jobs",
            "GET /jobs/{job_id}": "Get job status",
            "DELETE /jobs/{job_id}": "Delete job",
            "GET /jobs/{job_id}/download": "Download result image",
            "GET /health": "Health check",
            "GET /admin/stats": "System statistics",
        },
    )


@router.post(
    "/jobs",
    response_model=CreateClothesRemovalResponse,
    status_code=201,
    summary="Create clothes removal job",
    description="Upload an image and start a clothes removal pipeline job.",
    responses={
        201: {"description": "Job created successfully"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def create_job(request: CreateClothesRemovalRequest) -> CreateClothesRemovalResponse:
    job_id = f"{JOB_ID_PREFIX}{uuid.uuid4().hex[:12]}"

    job = ClothesRemovalJob(
        job_id=job_id,
        request=request.model_dump(),
    )

    store.save_job(job_id, job.model_dump(mode="json"))

    worker = get_worker()
    worker.start()

    return CreateClothesRemovalResponse(
        job_id=job_id,
        status="queued",
        message="Clothes removal job started",
    )


@router.get(
    "/jobs",
    response_model=ListJobsResponse,
    summary="List all jobs",
    description="Returns a paginated list of all clothes removal jobs.",
    responses={
        200: {"description": "Job list returned"},
    },
)
async def list_jobs(
    limit: int = Query(default=50, ge=1, le=200, description="Maximum jobs to return"),
    offset: int = Query(default=0, ge=0, description="Number of jobs to skip"),
) -> ListJobsResponse:
    jobs = store.list_jobs()
    sliced = jobs[offset : offset + limit]
    return ListJobsResponse(
        jobs=[
            JobListItem(
                job_id=j["job_id"],
                status=j["status"],
                progress=j.get("progress", 0),
                objects_detected=j.get("objects_detected"),
                created_at=j.get("created_at"),
            )
            for j in sliced
        ],
        total=len(jobs),
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
    description="Get the current status and progress of a clothes removal job.",
    responses={
        200: {"description": "Job status"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
async def get_job_status(job_id: str) -> JobStatusResponse:
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
        result_path=job_data.get("result_path"),
    )


@router.delete(
    "/jobs/{job_id}",
    response_model=DeleteJobResponse,
    summary="Delete job",
    description="Delete a clothes removal job and its output files.",
    responses={
        200: {"description": "Job deleted"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
async def delete_job(job_id: str) -> DeleteJobResponse:
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
    return DeleteJobResponse(
        message=f"Job {job_id} deleted",
        job_id=job_id,
    )
