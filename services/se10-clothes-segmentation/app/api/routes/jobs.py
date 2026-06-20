"""Job management routes for SE10 Clothes Segmentation.

Redis connection is deferred to first request — tests run without Redis.
Routes ordered: static paths (/, /stats) BEFORE parameterized (/{job_id}).
"""
from __future__ import annotations

import threading
from typing import Any

from common.log_utils import get_logger

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.domain.models import ErrorResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])

_job_manager: Any = None
_job_manager_lock = threading.Lock()


def _get_job_manager(job_manager: Any = None) -> Any:
    """Lazy-create JobManager with Redis connection (thread-safe).

    Args:
        job_manager: Optional override for DI/testing. If provided, sets the
                     module-level instance and returns it.
    """
    global _job_manager
    if job_manager is not None:
        _job_manager = job_manager
        return _job_manager

    if _job_manager is not None:
        return _job_manager

    with _job_manager_lock:
        if _job_manager is not None:
            return _job_manager

        from common.job_utils.store import JobRedisStore
        from common.job_utils.manager import JobManager
        from common.redis_utils import ResilientRedisStore

        settings = get_settings()
        redis_store = ResilientRedisStore(redis_url=settings.redis_url)
        job_store = JobRedisStore(
            redis_store=redis_store,
            service_name="se10-clothes-segmentation",
            ttl_hours=settings.cache_ttl_hours,
        )
        _job_manager = JobManager(store=job_store)
        return _job_manager


def _unavailable() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=ErrorResponse(error="SERVICE_UNAVAILABLE", message="Job service unavailable").model_dump(),
    )


@router.get(
    "/",
    response_model=None,
    responses={
        200: {"description": "List of jobs"},
        503: {"model": ErrorResponse, "description": "Redis unavailable"},
    },
)
async def list_jobs(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Any:
    """List jobs with optional status filter."""
    try:
        mgr = _get_job_manager()
        from common.job_utils.models import JobListResponse
        jobs = mgr.list_jobs(status=status, limit=limit, offset=offset)
        return JobListResponse(jobs=jobs, total=len(jobs), page=(offset // limit) + 1, page_size=limit)
    except Exception as e:
        logger.warning("Jobs unavailable (Redis not connected): %s", e)
        return _unavailable()


@router.get(
    "/stats",
    response_model=None,
    responses={
        200: {"description": "Job statistics"},
        503: {"model": ErrorResponse, "description": "Redis unavailable"},
    },
)
async def get_stats() -> Any:
    """Get job statistics."""
    try:
        mgr = _get_job_manager()
        return mgr.get_stats()
    except Exception as e:
        logger.warning("Jobs unavailable (Redis not connected): %s", e)
        return _unavailable()


@router.get(
    "/{job_id}",
    response_model=None,
    responses={
        200: {"description": "Job status"},
        404: {"model": ErrorResponse, "description": "Job not found"},
        410: {"model": ErrorResponse, "description": "Job expired"},
        503: {"model": ErrorResponse, "description": "Redis unavailable"},
    },
)
async def get_job(job_id: str) -> Any:
    """Get job status by ID."""
    from common.job_utils.exceptions import JobNotFoundError, JobExpiredError

    try:
        mgr = _get_job_manager()
        return mgr.get_job(job_id)
    except JobNotFoundError:
        return JSONResponse(status_code=404, content=ErrorResponse(error="JOB_NOT_FOUND", message=f"Job {job_id} not found").model_dump())
    except JobExpiredError:
        return JSONResponse(status_code=410, content=ErrorResponse(error="JOB_EXPIRED", message=f"Job {job_id} has expired").model_dump())
    except Exception as e:
        logger.warning("Jobs unavailable (Redis not connected): %s", e)
        return _unavailable()


@router.delete(
    "/{job_id}",
    response_model=None,
    responses={
        200: {"description": "Job deleted"},
        404: {"model": ErrorResponse, "description": "Job not found"},
        503: {"model": ErrorResponse, "description": "Redis unavailable"},
    },
)
async def delete_job(job_id: str) -> Any:
    """Delete a job by ID."""
    from common.job_utils.exceptions import JobNotFoundError

    try:
        mgr = _get_job_manager()
        mgr.delete_job(job_id)
        return {"message": f"Job {job_id} deleted", "job_id": job_id}
    except JobNotFoundError:
        return JSONResponse(status_code=404, content=ErrorResponse(error="JOB_NOT_FOUND", message=f"Job {job_id} not found").model_dump())
    except Exception as e:
        logger.warning("Jobs unavailable (Redis not connected): %s", e)
        return _unavailable()
