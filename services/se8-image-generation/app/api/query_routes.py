"""Query routes for SE8 Image Engine.

Handles job status queries, queue info, history, and outputs listing.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Response

from app.api.api_utils import generate_async_output
from app.domain.models import (
    AsyncJobResponse,
    JobHistoryInfo,
    JobHistoryResponse,
    JobQueueInfo,
)
from app.domain.task_models import TaskType
import app.services.worker as _worker_mod

logger = logging.getLogger(__name__)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

router = APIRouter(tags=["Query"])


@router.get("/v1/generation/query-job", response_model=AsyncJobResponse)
def query_job(job_id: str, require_step_preview: bool = False):
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
            content=content, media_type="application/json", status_code=404
        )
    return generate_async_output(queue_task, require_step_preview)


@router.get("/v1/generation/job-queue", response_model=JobQueueInfo)
def job_queue():
    """Query job queue info."""
    info = _worker_mod.worker_queue.get_queue_info()
    return JobQueueInfo(**info)


@router.get(
    "/v1/generation/job-history",
    response_model=JobHistoryResponse,
)
def job_history(
    job_id: Optional[str] = None,
    page: int = 0,
    page_size: int = 20,
    delete: bool = False,
):
    """Query historical job data."""
    if delete and job_id:
        task = _worker_mod.worker_queue.get_task(job_id, include_history=True)
        if task and task in _worker_mod.worker_queue.history:
            _worker_mod.worker_queue.history.remove(task)
            _worker_mod.worker_queue._cleanup_output_files(task)
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


@router.get("/v1/generation/outputs")
def list_outputs():
    """List all output images grouped by date."""
    from app.core.config import get_settings

    settings = get_settings()
    output_dir = settings.output_dir

    days = []
    if not os.path.isdir(output_dir):
        return {"days": []}

    for date_dir in sorted(os.listdir(output_dir), reverse=True):
        full = os.path.join(output_dir, date_dir)
        if not os.path.isdir(full):
            continue
        files = []
        for fname in sorted(os.listdir(full)):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in IMAGE_EXTS:
                continue
            fpath = os.path.join(full, fname)
            files.append(
                {
                    "name": fname,
                    "url": f"/files/{date_dir}/{fname}",
                    "size": os.path.getsize(fpath),
                }
            )
        if files:
            days.append({"date": date_dir, "files": files})
    return {"days": days}
