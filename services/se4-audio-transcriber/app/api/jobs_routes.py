from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Path as PathParam, Query, Request, UploadFile
from fastapi.responses import FileResponse

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from app.core.config import get_core, get_supported_languages, is_language_supported
from app.domain.models import Job, JobStatus, TranscriptionResponse, WhisperEngine
from app.api.schemas import (
    DeleteJobResponse,
    OrphanCleanupResponse,
    OrphanedJobsResponse,
    TextResponse,
)
from app.domain.interfaces import IJobStore
from app.infrastructure.dependencies import get_job_store as _get_job_store_dep, job_store, processor
from app.shared.exceptions import AudioTranscriptionException, ServiceException
from app.shared.file_upload_handler import FileUploadHandler, FileUploadError
from app.shared.job_creation_service import JobCreationService

if TYPE_CHECKING:
    from app.services.processor import TranscriptionProcessor

logger = get_logger(__name__)
settings = get_core()

router = APIRouter(tags=["Jobs"])


def submit_processing_task(job: Job, store: Any) -> None:
    """Submit job to Celery with asyncio fallback."""
    try:
        from app.infrastructure.celery_tasks import transcribe_audio_task

        task_result = transcribe_audio_task.apply_async(
            args=[job.model_dump()],
            task_id=job.id
        )
        logger.info(f"📤 Job {job.id} enviado para Celery worker: {task_result.id}")

    except Exception as e:
        logger.error(f"❌ Erro ao enviar job {job.id} para Celery, fallback direto")


@router.post("/jobs", summary="Create transcription job", response_model=Job, responses={400: {"description": "Invalid input or language not supported"}, 500: {"description": "Internal server error"}})
async def create_transcription_job(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language_in: str = Form("auto"),
    language_out: str | None = Form(None),
    engine: WhisperEngine = Form(WhisperEngine.FASTER_WHISPER),
) -> Job:

    if not is_language_supported(language_in):
        supported = get_supported_languages()
        raise HTTPException(status_code=400, detail={"error": "Linguagem de entrada não suportada", "language_provided": language_in, "supported_languages": supported[:10], "total_supported": len(supported), "note": "Use GET /languages para ver todas as linguagens suportadas"})

    if language_out is not None:
        if not is_language_supported(language_out):
            supported = get_supported_languages()
            raise HTTPException(status_code=400, detail={"error": "Linguagem de saída não suportada", "language_provided": language_out, "supported_languages": supported[:10], "total_supported": len(supported), "note": "Use GET /languages para ver todas as linguagens suportadas"})
        if language_out == language_in and language_in != "auto":
            logger.warning(f"language_out='{language_out}' igual a language_in='{language_in}', tradução não será aplicada")

    content = await file.read()

    upload_handler = FileUploadHandler(settings['upload_dir'])
    creation_service = JobCreationService(
        job_store=_get_job_store_dep(),
        upload_handler=upload_handler,
        submit_task_fn=submit_processing_task,
    )

    try:
        created_job = await creation_service.create_or_resume_job(
            file_content=content,
            original_filename=file.filename,
            language_in=language_in,
            language_out=language_out,
            engine=engine,
        )
        logger.info(f"Job de transcrição criado ou retomado: {created_job.id}")
        return created_job

    except FileUploadError as e:
        raise HTTPException(status_code=400 if not content else 500, detail=str(e))


@router.get("/jobs", summary="List jobs", response_model=list[Job])
async def list_jobs(
    limit: int = Query(20, ge=1, le=200, description="Quantidade maxima de jobs retornados.", examples=[20, 50]),
    job_store: IJobStore = Depends(job_store),
) -> list[Job]:
    """List recent transcription jobs."""
    return job_store.list_jobs(limit)


@router.get("/jobs/{job_id}", summary="Get job status", response_model=Job, responses={404: {"description": "Job not found"}, 410: {"description": "Job expired"}})
async def get_job_status(
    job_id: str = PathParam(..., description="ID do job de transcricao (prefixo esperado: at_).", examples=["at_abc123"]),
    job_store: IJobStore = Depends(job_store),
) -> Job:
    """Retrieve the current status and details of a transcription job."""
    job = job_store.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expirado")

    return job


@router.get("/jobs/{job_id}/download", summary="Download transcription file", responses={404: {"description": "Job or file not found"}, 410: {"description": "Job expired"}, 425: {"description": "Transcription not ready"}})
async def download_file(
    job_id: str = PathParam(..., description="ID do job concluido para download do arquivo SRT.", examples=["at_abc123"]),
    job_store: IJobStore = Depends(job_store),
) -> FileResponse:
    """Download the transcription output file for a completed job."""
    job = job_store.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expirado")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=425,
            detail=f"Transcrição não pronta. Status: {job.status}"
        )

    file_path = Path(job.output_file) if job.output_file else None
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    return FileResponse(
        path=file_path,
        filename=f"transcription_{job_id}.srt",
        media_type='text/plain'
    )


@router.get("/jobs/{job_id}/text", summary="Get transcription text", response_model=TextResponse, responses={404: {"description": "Job not found"}, 425: {"description": "Transcription not ready"}})
async def get_transcription_text(
    job_id: str = PathParam(..., description="ID do job concluido para retorno do texto puro.", examples=["at_abc123"]),
    job_store: IJobStore = Depends(job_store),
) -> dict[str, Any]:
    """Retrieve the plain text transcription for a completed job."""
    job = job_store.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=425,
            detail=f"Transcrição não pronta. Status: {job.status}"
        )

    return {"text": job.transcription_text or ""}


@router.get("/jobs/{job_id}/transcription", summary="Get full transcription", response_model=TranscriptionResponse, responses={404: {"description": "Job not found"}, 410: {"description": "Job expired"}, 425: {"description": "Transcription not ready"}, 500: {"description": "Segments not available"}})
async def get_full_transcription(
    job_id: str = PathParam(..., description="ID do job concluido para retorno completo da transcricao.", examples=["at_abc123"]),
    job_store: IJobStore = Depends(job_store),
) -> TranscriptionResponse:
    job = job_store.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expirado")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=425,
            detail=f"Transcrição não pronta. Status: {job.status}"
        )

    segments = job.transcription_segments or []
    duration = segments[-1].end if segments else 0.0

    processing_time = None
    if job.completed_at and job.created_at:
        processing_time = (job.completed_at - job.created_at).total_seconds()

    was_translated = job.language_out is not None and job.language_out != job.language_in

    return TranscriptionResponse(
        transcription_id=job.id,
        filename=job.filename or "unknown",
        language=job.language_detected or job.language_in,
        language_detected=job.language_detected,
        language_out=job.language_out,
        was_translated=was_translated,
        full_text=job.transcription_text or "",
        segments=segments,
        total_segments=len(segments),
        duration=duration,
        processing_time=processing_time
    )


@router.delete("/jobs/{job_id}", summary="Delete job", response_model=DeleteJobResponse, responses={404: {"description": "Job not found"}, 500: {"description": "Internal server error"}})
async def delete_job(
    job_id: str = PathParam(..., description="ID do job a ser removido (inclui arquivos associados).", examples=["at_abc123"]),
    job_store: IJobStore = Depends(job_store),
) -> dict[str, Any]:
    """Delete a transcription job and its associated files."""
    job = job_store.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    try:
        files_deleted = 0

        if job.input_file:
            input_path = Path(job.input_file)
            if input_path.exists():
                input_path.unlink()
                files_deleted += 1
                logger.info(f"🗑️ Arquivo de entrada removido: {input_path.name}")

        if job.output_file:
            output_path = Path(job.output_file)
            if output_path.exists():
                output_path.unlink()
                files_deleted += 1
                logger.info(f"🗑️ Arquivo de saída removido: {output_path.name}")

        job_store.delete_job(job_id)
        logger.info(f"🗑️ Job {job_id} removido do Redis")

        return {
            "message": "Job removido com sucesso",
            "job_id": job_id,
            "files_deleted": files_deleted
        }

    except Exception as e:
        logger.error(f"❌ Erro ao remover job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao remover job: {str(e)}"
        )


@router.get("/jobs/orphaned", summary="Get orphaned jobs", response_model=OrphanedJobsResponse, responses={500: {"description": "Internal server error"}})
async def get_orphaned_jobs(
    max_age_minutes: int = Query(
        30,
        ge=1,
        le=1440,
        description="Tempo maximo (em minutos) para considerar um job de processing como orfao.",
        examples=[30, 60],
    ),
    job_store: IJobStore = Depends(job_store),
) -> dict[str, Any]:
    """Find transcription jobs stuck in processing beyond the specified age."""
    try:
        orphaned = await job_store.find_orphaned_jobs(max_age_minutes=max_age_minutes)

        orphaned_info: list[dict[str, Any]] = []
        for job in orphaned:
            reference_time = job.started_at or job.updated_at or job.created_at
            age_minutes = (now_brazil() - reference_time).total_seconds() / 60
            orphaned_info.append({
                "job_id": job.id,
                "status": job.status.value if hasattr(job.status, "value") else str(job.status),
                "created_at": job.created_at.isoformat(),
                "updated_at": reference_time.isoformat(),
                "age_minutes": round(age_minutes, 2),
                "filename": job.filename if hasattr(job, 'filename') else None
            })

        return {
            "status": "success",
            "count": len(orphaned),
            "max_age_minutes": max_age_minutes,
            "orphaned_jobs": orphaned_info
        }

    except Exception as e:
        logger.error(f"Error getting orphaned jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get orphaned jobs: {str(e)}")


@router.post("/jobs/orphaned/cleanup", summary="Cleanup orphaned jobs", response_model=OrphanCleanupResponse, responses={500: {"description": "Internal server error"}})
async def cleanup_orphaned_jobs_endpoint(
    max_age_minutes: int = Query(
        30,
        ge=1,
        le=1440,
        description="Tempo maximo (em minutos) para detectar jobs orfaos.",
        examples=[30, 120],
    ),
    mark_as_failed: bool = Query(
        True,
        description="Se true, marca jobs orfaos como failed. Se false, remove os jobs.",
    ),
    job_store: IJobStore = Depends(job_store),
) -> dict[str, Any]:
    try:
        orphaned = await job_store.find_orphaned_jobs(max_age_minutes=max_age_minutes)

        if not orphaned:
            return {
                "status": "success",
                "message": "No orphaned jobs found",
                "count": 0,
                "actions": []
            }

        actions: list[dict[str, Any]] = []
        space_freed = 0

        for job in orphaned:
            reference_time = job.started_at or job.updated_at or job.created_at
            age_minutes = (now_brazil() - reference_time).total_seconds() / 60

            files_deleted: list[dict[str, Any]] = []
            errors: list[str] = []

            if job.input_file:
                try:
                    audio_path = Path(job.input_file)
                    if audio_path.exists() and audio_path.is_file():
                        size_mb = audio_path.stat().st_size / (1024 * 1024)
                        audio_path.unlink(missing_ok=True)
                        files_deleted.append({"file": str(audio_path), "size_mb": round(size_mb, 2)})
                        space_freed += size_mb
                except Exception as e:
                    errors.append(f"Failed to delete input audio: {str(e)}")
                    logger.warning(f"Failed to delete audio file: {e}")

            try:
                transcription_path = Path(job.output_file) if job.output_file else None
                if transcription_path and transcription_path.exists() and transcription_path.is_file():
                    size_mb = transcription_path.stat().st_size / (1024 * 1024)
                    transcription_path.unlink(missing_ok=True)
                    files_deleted.append({"file": str(transcription_path), "size_mb": round(size_mb, 2)})
                    space_freed += size_mb
            except Exception as e:
                errors.append(f"Failed to delete transcription: {str(e)}")
                logger.warning(f"Failed to delete transcription file: {e}")

            try:
                temp_dir = Path("./data/temp")
                if temp_dir.exists() and temp_dir.is_dir():
                    for temp_file in temp_dir.glob(f"*{job.id}*"):
                        if temp_file.is_file():
                            try:
                                size_mb = temp_file.stat().st_size / (1024 * 1024)
                                temp_file.unlink(missing_ok=True)
                                files_deleted.append({"file": str(temp_file), "size_mb": round(size_mb, 2)})
                                space_freed += size_mb
                            except Exception as e:
                                errors.append(f"Failed to delete temp {temp_file.name}: {str(e)}")
                                logger.warning(f"Failed to delete temp file: {e}")
            except Exception as e:
                errors.append(f"Failed to scan temp directory: {str(e)}")
                logger.warning(f"Failed to scan temp directory: {e}")

            if mark_as_failed:
                try:
                    job.status = JobStatus.FAILED
                    job.error_message = f"Job orphaned: stuck in processing for {age_minutes:.1f} minutes (auto-recovery)"
                    job.completed_at = now_brazil()
                    job.updated_at = now_brazil()
                    job_store.update_job(job)

                    actions.append({
                        "job_id": job.id,
                        "action": "marked_as_failed",
                        "age_minutes": round(age_minutes, 2),
                        "files_deleted": files_deleted,
                        "reason": job.error_message,
                        "errors": errors if errors else None
                    })
                except Exception as e:
                    errors.append(f"Failed to mark job as failed: {str(e)}")
                    logger.error(f"Failed to mark job {job.id} as failed: {e}", exc_info=True)
                    actions.append({
                        "job_id": job.id,
                        "action": "failed_to_update",
                        "age_minutes": round(age_minutes, 2),
                        "files_deleted": files_deleted,
                        "errors": errors
                    })
            else:
                try:
                    job_store.delete_job(job.id)

                    actions.append({
                        "job_id": job.id,
                        "action": "deleted",
                        "age_minutes": round(age_minutes, 2),
                        "files_deleted": files_deleted,
                        "errors": errors if errors else None
                    })
                except Exception as e:
                    errors.append(f"Failed to delete job: {str(e)}")
                    logger.error(f"Failed to delete job {job.id}: {e}", exc_info=True)
                    actions.append({
                        "job_id": job.id,
                        "action": "failed_to_delete",
                        "age_minutes": round(age_minutes, 2),
                        "files_deleted": files_deleted,
                        "errors": errors
                    })

            logger.info(
                f"🧹 Orphaned job {'marked as failed' if mark_as_failed else 'deleted'}: "
                f"{job.id} (age: {age_minutes:.1f}min, files: {len(files_deleted)}, "
                f"space freed: {sum(f['size_mb'] for f in files_deleted):.2f}MB)"
            )

        return {
            "status": "success",
            "message": f"Cleaned up {len(orphaned)} orphaned job(s)",
            "count": len(orphaned),
            "mode": "mark_as_failed" if mark_as_failed else "delete",
            "max_age_minutes": max_age_minutes,
            "space_freed_mb": round(space_freed, 2),
            "actions": actions
        }

    except Exception as e:
        logger.error(f"Error cleaning up orphaned jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cleanup orphaned jobs: {str(e)}")
