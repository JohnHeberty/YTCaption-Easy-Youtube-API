"""Download routes for SE11 Clothes Removal."""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.api.schemas import ErrorResponse
from app.infrastructure.redis_store import ClothesRemovalJobStore

router = APIRouter(tags=["Jobs"])
store = ClothesRemovalJobStore()


@router.get(
    "/jobs/{job_id}/download",
    summary="Download result image",
    description="Download the result PNG image for a completed job.",
    responses={
        200: {"description": "PNG image file"},
        400: {"model": ErrorResponse, "description": "Job not completed"},
        404: {"model": ErrorResponse, "description": "Job or file not found"},
    },
)
async def download_result(job_id: str) -> FileResponse:
    job_data = store.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job_data["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not completed (status: {job_data['status']})",
        )

    result_path = job_data.get("result_path")
    if not result_path or not os.path.exists(result_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result file not found")

    return FileResponse(
        path=result_path,
        filename=f"{job_id}_result.png",
        media_type="image/png",
    )
