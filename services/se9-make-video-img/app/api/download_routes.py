"""Download route for completed videos."""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.models import VideoJobStatus
from app.infrastructure.redis_store import get_video_job_store

router = APIRouter()
store = get_video_job_store()


@router.get("/download/{job_id}")
async def download_video(job_id: str) -> FileResponse:
    """Download the completed video file."""
    job_data = store.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    if job_data["status"] != VideoJobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job_data['status']}",
        )

    video_path = job_data.get("video_path")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=f"{job_id}.mp4",
    )
