"""Query routes for SE8 Image Engine.

Handles job status queries, queue info, history, and outputs listing.
"""

from __future__ import annotations
from common.log_utils import get_logger

import os

from fastapi import APIRouter, Response, status

from app.api.api_utils import generate_async_output
from app.api.schemas import (
    ErrorResponse,
    ListOutputsResponse,
    OutputDateGroup,
    OutputFileInfo,
)
from app.domain.models import (
    AsyncJobResponse,
    JobHistoryInfo,
    JobHistoryResponse,
    JobQueueInfo,
)
from app.domain.task_models import TaskType
import app.services.worker as _worker_mod

logger = get_logger(__name__)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

router = APIRouter(tags=["Query"])


@router.get(
    "/v1/generation/query-job",
    response_model=AsyncJobResponse,
    responses={404: {"model": ErrorResponse}},
)
def query_job(job_id: str, require_step_preview: bool = False) -> Response | AsyncJobResponse:
    """Query async generation job status."""
    queue_task = _worker_mod.worker_queue.get_task(job_id, True)
    if queue_task is None:
        result = AsyncJobResponse(
            job_id="",
            job_type=TaskType.NOT_FOUND.value,
            job_stage="ERROR",
            job_progress=0,
            job_status="Job not found",
        )
        content = result.model_dump_json()
        return Response(
            content=content, media_type="application/json", status_code=status.HTTP_404_NOT_FOUND
        )
    return generate_async_output(queue_task, require_step_preview)


@router.get("/v1/generation/job-queue", response_model=JobQueueInfo)
def job_queue() -> JobQueueInfo:
    """Query job queue info."""
    info = _worker_mod.worker_queue.get_queue_info()
    return JobQueueInfo(**info)


@router.get(
    "/v1/generation/job-history",
    response_model=JobHistoryResponse,
)
def job_history(
    job_id: str | None = None,
    page: int = 0,
    page_size: int = 20,
    delete: bool = False,
) -> Response | JobHistoryResponse:
    """Query historical job data."""
    if delete and job_id:
        result = _worker_mod.worker_queue.get_history(job_id=job_id, delete=True)
        if "deleted" in result:
            return Response(
                content='{"message": "Deleted"}',
                media_type="application/json",
            )
        return Response(
            content='{"message": "Not found"}',
            media_type="application/json",
        )

    result = _worker_mod.worker_queue.get_history(job_id, page, page_size)
    queue = [
        JobHistoryInfo(**item) for item in result.get("queue", [])
    ]
    history = [
        JobHistoryInfo(**item) for item in result.get("history", [])
    ]
    return JobHistoryResponse(queue=queue, history=history)


@router.get("/v1/generation/outputs", response_model=ListOutputsResponse)
def list_outputs() -> ListOutputsResponse:
    """List all output images grouped by date."""
    from app.core.config import get_settings

    settings = get_settings()
    output_dir = settings.output_dir

    days: list[OutputDateGroup] = []
    if not os.path.isdir(output_dir):
        return ListOutputsResponse(days=[])

    for date_dir in sorted(os.listdir(output_dir), reverse=True):
        full = os.path.join(output_dir, date_dir)
        if not os.path.isdir(full):
            continue
        files: list[OutputFileInfo] = []
        for fname in sorted(os.listdir(full)):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in IMAGE_EXTS:
                continue
            fpath = os.path.join(full, fname)
            files.append(
                OutputFileInfo(
                    name=fname,
                    url=f"/files/{date_dir}/{fname}",
                    size=os.path.getsize(fpath),
                )
            )
        if files:
            days.append(OutputDateGroup(date=date_dir, files=files))
    return ListOutputsResponse(days=days)
