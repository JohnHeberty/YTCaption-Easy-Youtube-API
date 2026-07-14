from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import FileResponse

from common.log_utils import get_logger

from app.api.schemas import (
    ErrorResponse,
    JobListResponse,
    JobResponse,
    DeleteJobResponse,
    JobDetailResponse,
)
from app.core.constants import DEFAULT_EXAGGERATION, DEFAULT_CFG_WEIGHT, DEFAULT_TEMPERATURE
from app.domain.models import AudioGenerationJob, JobStatus
from app.domain.interfaces import IJobStore, ITTSGenerator, IVoiceStore
from app.domain.exceptions import TextValidationError, VoiceProfileNotFound
from app.infrastructure.dependencies import job_store, generator, voice_store

logger = get_logger(__name__)
router = APIRouter(tags=["Jobs"])


@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=201,
    responses={422: {"model": ErrorResponse}},
)
async def create_generation_job(
    text: str = Form(...),
    voice_id: str | None = Form(None),
    exaggeration: float = Form(DEFAULT_EXAGGERATION),
    cfg_weight: float = Form(DEFAULT_CFG_WEIGHT),
    temperature: float = Form(DEFAULT_TEMPERATURE),
    normalize_text: bool = Form(True),
    store: IJobStore = Depends(job_store),
    gen: ITTSGenerator = Depends(generator),
    voice_store_dep: IVoiceStore = Depends(voice_store),
) -> JobResponse:
    if voice_id:
        profile = voice_store_dep.get_profile(voice_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Voice profile not found: {voice_id}")

    try:
        job = AudioGenerationJob.create_new(
            text=text,
            voice_id=voice_id,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
            temperature=temperature,
            normalize_text=normalize_text,
        )
    except TextValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    store.save_job(job)

    try:
        from app.infrastructure.celery_tasks import generate_audio_task

        generate_audio_task.apply_async(
            args=[job.model_dump()], task_id=job.id, retry=False
        )
    except Exception as e:
        logger.warning(f"Celery unavailable, job {job.id} queued locally: {e}")

    return JobResponse(
        success=True,
        job_id=job.id,
        status=job.status.value,
        message="Audio generation job created",
    )


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    store: IJobStore = Depends(job_store),
) -> JobListResponse:
    jobs = store.list_jobs(limit)
    details: list[JobDetailResponse] = []
    for j in jobs:
        data = j.model_dump()
        for key in ("created_at", "started_at", "completed_at"):
            val = data.get(key)
            if hasattr(val, "isoformat"):
                data[key] = val.isoformat()
        details.append(JobDetailResponse(**data))
    return JobListResponse(jobs=details, total=len(jobs))


@router.get(
    "/jobs/{job_id}",
    response_model=JobDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_job_status(
    job_id: str,
    store: IJobStore = Depends(job_store),
) -> JobDetailResponse:
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expired")
    data = job.model_dump()
    # Convert datetime objects to ISO strings for schema compatibility
    for key in ("created_at", "started_at", "completed_at"):
        val = data.get(key)
        if hasattr(val, "isoformat"):
            data[key] = val.isoformat()
    return JobDetailResponse(**data)


@router.get("/jobs/{job_id}/download")
async def download_audio(
    job_id: str,
    store: IJobStore = Depends(job_store),
) -> FileResponse:
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expired")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=425, detail=f"Audio not ready. Status: {job.status.value}"
        )
    if not job.output_file or not Path(job.output_file).exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(
        path=job.output_file,
        filename=f"generated_{job_id}.wav",
        media_type="audio/wav",
    )


@router.delete(
    "/jobs/{job_id}",
    response_model=DeleteJobResponse,
    responses={404: {"model": ErrorResponse}},
)
async def delete_job(
    job_id: str,
    store: IJobStore = Depends(job_store),
) -> DeleteJobResponse:
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    files_deleted = 0
    if job.output_file:
        path = Path(job.output_file)
        if path.exists():
            path.unlink()
            files_deleted += 1

    store.delete_job(job_id)
    return DeleteJobResponse(
        message="Job removed successfully",
        job_id=job_id,
        files_deleted=files_deleted,
    )
