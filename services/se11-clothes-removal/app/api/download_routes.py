"""Download routes for SE11 Clothes Removal."""
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.infrastructure.redis_store import ClothesRemovalJobStore

router = APIRouter()
store = ClothesRemovalJobStore()


@router.get("/jobs/{job_id}/download")
async def download_result(job_id: str):
    """Download the result image for a completed job."""
    job_data = store.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    if job_data["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed (status: {job_data['status']})",
        )

    result_path = job_data.get("result_path")
    if not result_path or not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="Result file not found")

    return FileResponse(
        path=result_path,
        filename=f"{job_id}_result.png",
        media_type="image/png",
    )
