"""
Standard FastAPI router factory for job endpoints.

Provides a turnkey router with the common CRUD endpoints all
services expose: GET job, GET job list, DELETE job, GET stats.

Usage:
    from common.job_utils.routes import create_job_router
    from common.job_utils.manager import JobManager

    router = create_job_router(job_manager=my_manager, service_name="video-downloader")
    app.include_router(router)
"""
import logging
from typing import Optional

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from common.job_utils.models import StandardJob, JobListResponse, ErrorResponse
from common.job_utils.manager import JobManager
from common.job_utils.exceptions import JobNotFoundError, JobExpiredError

logger = logging.getLogger(__name__)


def create_job_router(
    job_manager: JobManager,
    service_name: str,
    prefix: str = "/jobs",
    enable_list: bool = True,
    enable_delete: bool = True,
    enable_stats: bool = True,
) -> APIRouter:
    """
    Create a standard job router with common endpoints.

    Args:
        job_manager: The JobManager instance for this service.
        service_name: Service name for tagging responses.
        prefix: Router path prefix (default /jobs).
        enable_list: Whether to include GET / (list jobs) endpoint.
        enable_delete: Whether to include DELETE /{job_id} endpoint.
        enable_stats: Whether to include GET /stats endpoint.

    Returns:
        APIRouter with standard job endpoints.
    """
    router = APIRouter(prefix=prefix, tags=[f"{service_name} - Jobs"])

    @router.get(
        "/{job_id}",
        response_model=StandardJob,
        responses={
            404: {"model": ErrorResponse},
            410: {"model": ErrorResponse},
        },
    )
    async def get_job(job_id: str):
        """Get job status by ID."""
        try:
            return job_manager.get_job(job_id)
        except JobNotFoundError:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ErrorResponse(
                    error="JOB_NOT_FOUND",
                    message=f"Job {job_id} not found",
                ).model_dump(),
            )
        except JobExpiredError:
            return JSONResponse(
                status_code=status.HTTP_410_GONE,
                content=ErrorResponse(
                    error="JOB_EXPIRED",
                    message=f"Job {job_id} has expired",
                ).model_dump(),
            )

    if enable_list:

        @router.get("/", response_model=JobListResponse)
        async def list_jobs(
            status_filter: Optional[str] = Query(None, alias="status"),
            limit: int = Query(50, ge=1, le=200),
            offset: int = Query(0, ge=0),
        ):
            """List jobs with optional status filter."""
            jobs = job_manager.list_jobs(status=status_filter, limit=limit, offset=offset)
            return JobListResponse(
                jobs=jobs,
                total=len(jobs),
                page=(offset // limit) + 1,
                page_size=limit,
            )

    if enable_delete:

        @router.delete(
            "/{job_id}",
            responses={404: {"model": ErrorResponse}},
        )
        async def delete_job(job_id: str):
            """Delete a job by ID."""
            try:
                job_manager.delete_job(job_id)
                return {"message": f"Job {job_id} deleted", "job_id": job_id}
            except JobNotFoundError:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content=ErrorResponse(
                        error="JOB_NOT_FOUND",
                        message=f"Job {job_id} not found",
                    ).model_dump(),
                )

    if enable_stats:

        @router.get("/stats")
        async def get_stats():
            """Get job statistics."""
            return job_manager.get_stats()

    return router