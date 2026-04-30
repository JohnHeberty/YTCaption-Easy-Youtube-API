"""
Jobs API endpoints for YouTube Search service.

This module contains job management endpoints:
- Get job status
- List jobs
- Delete job
- Download results
- Wait for job completion
"""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from fastapi.responses import Response

from app.core.config import get_settings
from app.core.constants import POLL_INTERVAL_SECONDS
from app.core.validators import ValidationError, TimeoutValidator, JobIdValidator
from app.domain.models import Job, JobListResponse, JobStatus, DeleteJobResponse
from app.infrastructure.redis_store import YouTubeSearchJobStore as RedisJobStore
from app.infrastructure.dependencies import get_job_store_override
from app.shared.exceptions import InvalidRequestError
from common.log_utils import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["Jobs"])

settings = get_settings()

def _validate_job_id(job_id: str) -> str:
    """
    Validate job_id format.

    Args:
        job_id: The job ID to validate

    Returns:
        Validated job ID

    Raises:
        InvalidRequestError: If job_id is invalid
    """
    try:
        return JobIdValidator.validate(job_id)
    except ValidationError as exc:
        raise InvalidRequestError(str(exc)) from exc

@router.get("/{job_id}", summary="Get job status", response_model=Job, responses={404: {"description": "Job not found"}})
async def get_job_status(
    job_id: str = Path(..., description="ID do job para consulta.", examples=["a1b2c3d4e5f6a7b8"]),
    store: RedisJobStore = Depends(get_job_store_override),
) -> Job:
    """Retrieve the current status and results of a search job."""
    _validate_job_id(job_id)

    job = store.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job

@router.get("/", summary="List jobs", response_model=JobListResponse)
async def list_jobs(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Quantidade máxima de jobs retornados.",
        examples=[20, 50, 100],
    ),
    store: RedisJobStore = Depends(get_job_store_override),
) -> JobListResponse:
    """List all search jobs with optional limit."""
    jobs = store.list_jobs(limit=limit)
    return JobListResponse(jobs=jobs, total=len(jobs))

@router.delete("/{job_id}", summary="Delete job", response_model=DeleteJobResponse, responses={404: {"description": "Job not found"}, 500: {"description": "Internal server error"}})
async def delete_job(
    job_id: str = Path(..., description="ID do job a ser removido.", examples=["a1b2c3d4e5f6a7b8"]),
    store: RedisJobStore = Depends(get_job_store_override),
) -> DeleteJobResponse:
    """Remove a search job and its associated data from Redis."""
    _validate_job_id(job_id)

    job = store.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        store.delete_job(job_id)
        logger.info(f"🗑️ Job {job_id} removed from Redis")

        return {"message": "Job removed successfully", "job_id": job_id}

    except Exception as exc:
        logger.error(f"❌ Error removing job {job_id}: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Error removing job: {str(exc)}"
        ) from exc

@router.get("/{job_id}/download", summary="Download results", responses={404: {"description": "Job or results not found"}, 410: {"description": "Job expired"}, 425: {"description": "Results not ready"}, 500: {"description": "Internal server error"}})
async def download_results(
    job_id: str = Path(..., description="ID do job para download dos resultados.", examples=["a1b2c3d4e5f6a7b8"]),
    store: RedisJobStore = Depends(get_job_store_override),
) -> Response:
    """Download completed search results as a JSON file."""
    _validate_job_id(job_id)

    try:
        job = store.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.is_expired:
            raise HTTPException(status_code=410, detail="Job expired")

        if job.status != JobStatus.COMPLETED:
            raise HTTPException(
                status_code=425, detail=f"Results not ready. Status: {job.status.value}"
            )

        if not job.result:
            raise HTTPException(status_code=404, detail="No results available")

        filename = f"youtube_search_{job.search_type.value}_{job_id}.json"
        result_json = json.dumps(job.result, indent=2, ensure_ascii=False)

        logger.info(f"📥 Downloading results for job {job_id}: {len(result_json)} bytes")

        return Response(
            content=result_json,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error downloading results: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.get("/{job_id}/wait", summary="Wait for job completion", response_model=Job, responses={404: {"description": "Job not found"}, 408: {"description": "Timeout waiting for job"}, 503: {"description": "Service unavailable"}, 500: {"description": "Internal server error"}})
async def wait_for_job_completion(
    job_id: str = Path(..., description="ID do job para aguardar conclusão.", examples=["a1b2c3d4e5f6a7b8"]),
    timeout: int = Query(
        default=600,
        ge=1,
        le=3600,
        description="Tempo máximo de espera em segundos.",
        examples=[60, 300, 600],
    ),
    store: RedisJobStore = Depends(get_job_store_override),
) -> Job:
    """Long-poll endpoint that waits for a search job to complete, fail, or timeout."""
    _validate_job_id(job_id)

    if store is None:
        raise HTTPException(status_code=503, detail="Job store not available")

    try:
        validated_timeout = TimeoutValidator.validate(timeout)
    except ValidationError as exc:
        raise InvalidRequestError(str(exc)) from exc

    from common.datetime_utils import now_brazil

    start_time = now_brazil()
    poll_interval = POLL_INTERVAL_SECONDS

    logger.info(
        f"Client waiting for job {job_id} completion (timeout: {validated_timeout}s)"
    )

    try:
        while (now_brazil() - start_time).total_seconds() < validated_timeout:
            job = store.get_job(job_id)

            if not job:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                elapsed = (now_brazil() - start_time).total_seconds()
                logger.info(
                    f"Job {job_id} finished with status {job.status.value} after {elapsed:.1f}s"
                )
                return job

            logger.debug(
                f"Job {job_id} still processing: {job.status.value} ({job.progress}%)"
            )
            await asyncio.sleep(poll_interval)

        # Timeout reached
        elapsed = (now_brazil() - start_time).total_seconds()
        logger.warning(f"Timeout waiting for job {job_id} after {elapsed:.1f}s")
        raise HTTPException(
            status_code=408,
            detail=f"Timeout waiting for job completion after {validated_timeout}s. "
            f"Use GET /jobs/{job_id} to check current status.",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error waiting for job: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
