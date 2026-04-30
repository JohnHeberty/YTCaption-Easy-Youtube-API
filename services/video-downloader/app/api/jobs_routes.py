"""
Standardized job API routes for video-downloader service using common.job_utils.
"""
from pathlib import Path
from typing import List

from common.datetime_utils import now_brazil
from common.log_utils import get_logger
from common.job_utils.models import ErrorResponse, JobStatus

from fastapi import APIRouter, HTTPException, Query, status, Depends
from fastapi.responses import FileResponse

from app.core.models import (
    DeleteJobResponse,
    OrphanedCleanupResponse,
    OrphanedJobsResponse,
    QueueInfoResponse,
    VideoDownloadJob,
    VideoDownloadJobCreatedResponse,
    VideoDownloadJobRequest,
)
from app.infrastructure.dependencies import get_job_store_override, get_downloader_override
from app.infrastructure.redis_store import VideoDownloadJobStore
from app.services.video_downloader import YDLPVideoDownloader

router = APIRouter(tags=["Jobs"])
logger = get_logger(__name__)


@router.post(
    "/jobs",
    summary="Create download job",
    description=(
        "Create a new video download job.\n\n"
        "Request body intentionally accepts only:\n"
        "- `url` (required)\n"
        "- `quality` (`best`, `worst`, `720p`, `480p`, `360p`, `audio`; default: `best`)\n\n"
        "All other fields shown in the job response are managed internally by the pipeline."
    ),
    response_model=VideoDownloadJobCreatedResponse,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}, 500: {"description": "Internal server error"}},
)
async def create_download_job(request: VideoDownloadJobRequest, store: VideoDownloadJobStore = Depends(get_job_store_override)):
    """Create a new video download job.

    Request body intentionally accepts only:
    - `url` (required)
    - `quality` (`best`, `worst`, `720p`, `480p`, `360p`, `audio`; default: `best`)

    All other fields shown in the job response are managed internally by the pipeline.
    """
    from app.infrastructure.celery_tasks import download_video_task
    from app.infrastructure.celery_config import celery_app

    try:
        logger.info(f"Creating download job for URL: {request.url}")
        try:
            inspect = celery_app.control.inspect(timeout=3.0)
            active_workers = inspect.active()
            if not active_workers or len(active_workers) == 0:
                logger.warning("No Celery workers available")
        except Exception:
            pass

        new_job = VideoDownloadJob.create_new(request.url, request.quality)
        existing_job = store.get_job(new_job.id)
        if existing_job:
            if existing_job.status == "completed":
                logger.info(f"Job {new_job.id} already completed")
                return VideoDownloadJobCreatedResponse.from_job(existing_job)
            elif existing_job.status in ("queued", "processing"):
                logger.info(f"Job {new_job.id} already processing")
                return VideoDownloadJobCreatedResponse.from_job(existing_job)
            elif existing_job.status == "failed":
                logger.info(f"Retrying failed job: {new_job.id}")
                existing_job.status = JobStatus.QUEUED
                existing_job.error_message = None
                existing_job.progress = 0.0
                store.update_job(existing_job)
                download_video_task.apply_async(args=[existing_job.model_dump(mode="json")], task_id=existing_job.id)
                return VideoDownloadJobCreatedResponse.from_job(existing_job)

        store.save_job(new_job)
        download_video_task.apply_async(args=[new_job.model_dump(mode="json")], task_id=new_job.id)
        logger.info(f"Download job created: {new_job.id}")
        return VideoDownloadJobCreatedResponse.from_job(new_job)

    except Exception as e:
        logger.error(f"Error creating download job: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/jobs/{job_id}", summary="Get job status", response_model=VideoDownloadJob, responses={404: {"model": ErrorResponse}, 410: {"model": ErrorResponse}})
async def get_job_status(job_id: str, store: VideoDownloadJobStore = Depends(get_job_store_override)):
    """Retrieve the current status and details of a download job."""
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expired")
    return job


@router.get("/jobs/{job_id}/download", summary="Download video file", responses={404: {"description": "Job or file not found"}, 410: {"description": "Job expired"}, 425: {"description": "Download not ready"}})
async def download_file(job_id: str, store: VideoDownloadJobStore = Depends(get_job_store_override), downloader: YDLPVideoDownloader = Depends(get_downloader_override)):
    """Download the video file for a completed job."""
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expired")
    if job.status.value not in ("completed",):
        raise HTTPException(status_code=425, detail=f"Download not ready. Status: {job.status}")

    fp = downloader.get_file_path(job)
    if not fp or not Path(str(fp)).exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path=str(fp), filename=job.filename or f"{job_id}.mp4", media_type='application/octet-stream')


@router.get("/jobs", summary="List jobs", response_model=List[VideoDownloadJob])
async def list_jobs(limit: int = Query(20, ge=1, le=200), store: VideoDownloadJobStore = Depends(get_job_store_override)):
    """List recent download jobs."""
    return store.list_jobs(limit)


@router.delete("/jobs/{job_id}", summary="Delete job", response_model=DeleteJobResponse, responses={404: {"model": ErrorResponse}})
async def delete_job(job_id: str, store: VideoDownloadJobStore = Depends(get_job_store_override)):
    """Delete a download job and its associated files."""
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    files_deleted = 0
    if job.file_path:
        try:
            fp = Path(job.file_path)
            if fp.exists():
                fp.unlink()
                files_deleted += 1
        except Exception:
            pass
    store.delete_job(job_id)
    return {"message": "Job deleted successfully", "job_id": job_id, "files_deleted": files_deleted}


@router.get("/jobs/orphaned", summary="Get orphaned jobs", response_model=OrphanedJobsResponse, responses={500: {"description": "Internal server error"}})
async def get_orphaned_jobs(
    max_age_minutes: int = Query(
        30,
        ge=1,
        description="Idade mínima em minutos para considerar um job órfão.",
        examples=[30, 60],
    ),
    store: VideoDownloadJobStore = Depends(get_job_store_override),
):
    """Find download jobs stuck in processing beyond the specified age."""
    orphaned = await store.find_orphaned_jobs(max_age_minutes=max_age_minutes)
    orphaned_info = []
    for job in orphaned:
        age = 0.0
        if job.started_at:
            age = (now_brazil() - job.started_at).total_seconds() / 60
        orphaned_info.append({
            "job_id": job.id,
            "status": str(job.status.value),
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "age_minutes": round(age, 2),
            "url": job.url,
        })
    return {"status": "success", "count": len(orphaned), "max_age_minutes": max_age_minutes, "orphaned_jobs": orphaned_info}


@router.post("/jobs/orphaned/cleanup", summary="Cleanup orphaned jobs", response_model=OrphanedCleanupResponse, responses={500: {"description": "Internal server error"}})
async def cleanup_orphaned_jobs(
    max_age_minutes: int = Query(
        30,
        ge=1,
        description="Idade mínima em minutos para selecionar jobs órfãos.",
        examples=[30, 90],
    ),
    mark_as_failed: bool = Query(
        True,
        description="Quando true marca jobs como failed; quando false remove do store.",
        examples=[True, False],
    ),
    store: VideoDownloadJobStore = Depends(get_job_store_override),
):
    """Mark or delete orphaned download jobs stuck in processing."""
    orphaned = await store.find_orphaned_jobs(max_age_minutes=max_age_minutes)
    if not orphaned:
        return {"status": "success", "message": "No orphaned jobs found", "count": 0, "actions": []}
    actions = []
    for job in orphaned:
        age = 0.0
        if job.started_at:
            age = (now_brazil() - job.started_at).total_seconds() / 60
        if mark_as_failed:
            job.mark_as_failed(f"Orphaned: stuck for {age:.1f} minutes")
            store.update_job(job)
            actions.append({"job_id": job.id, "action": "marked_as_failed", "age_minutes": round(age, 2)})
        else:
            store.delete_job(job.id)
            actions.append({"job_id": job.id, "action": "deleted", "age_minutes": round(age, 2)})
    return {"status": "success", "message": f"Cleaned up {len(orphaned)} orphaned job(s)", "count": len(orphaned), "mode": "mark_as_failed" if mark_as_failed else "delete", "actions": actions}