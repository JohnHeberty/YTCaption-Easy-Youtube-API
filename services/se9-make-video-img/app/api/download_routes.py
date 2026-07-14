"""Download route for completed videos."""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.api.schemas import ErrorResponse, VideoJobStatus
from app.infrastructure.redis_store import get_video_job_store

router = APIRouter(tags=["Download"])
store = get_video_job_store()


@router.get(
    "/download/{job_id}",
    summary="Download completed video",
    description=(
        "Download the final video file (MP4) for a completed job.\n\n"
        "**Prerequisites:** Job must have `status=completed`. "
        "Use `GET /jobs/{job_id}` to poll until completed.\n\n"
        "**Response:** Binary MP4 file with `Content-Disposition` header."
    ),
    responses={
        200: {"description": "Video file (MP4)", "content": {"video/mp4": {}}},
        400: {"model": ErrorResponse, "description": "Job not completed"},
        404: {"model": ErrorResponse, "description": "Job or video file not found"},
    },
)
async def download_video(job_id: str) -> FileResponse:
    job_data = store.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job_data["status"] != VideoJobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not completed. Current status: {job_data['status']}",
        )

    video_path = job_data.get("video_path")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found")

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=f"{job_id}.mp4",
    )
