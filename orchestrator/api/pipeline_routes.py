"""
Pipeline API routes for the orchestrator service.

This module contains the API endpoints for pipeline processing,
broken down into smaller, testable functions.
"""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

from common.log_utils import get_logger
from domain.models import PipelineRequest, PipelineResponse, PipelineJob
from core.config import get_settings
from infrastructure.redis_store import get_store
from infrastructure.dependency_injection import get_pipeline_orchestrator
from core.exceptions import ValidationError, JobCreationError, RedisConnectionError
from core.constants import Timeouts

logger = get_logger(__name__)
router = APIRouter()
settings = get_settings()


async def _create_pipeline_job(request: PipelineRequest) -> PipelineJob:
    """
    Create a new pipeline job from the request.

    Args:
        request: Pipeline request with YouTube URL and configuration

    Returns:
        New pipeline job instance

    Raises:
        ValidationError: If request data is invalid
        JobCreationError: If job creation fails
    """
    try:
        job = PipelineJob.create_new(
            youtube_url=request.youtube_url,
            language=request.language or settings["default_language"],
            language_out=request.language_out,
            remove_noise=request.remove_noise
            if request.remove_noise is not None
            else settings["default_remove_noise"],
            convert_to_mono=request.convert_to_mono
            if request.convert_to_mono is not None
            else settings["default_convert_mono"],
            apply_highpass_filter=request.apply_highpass_filter
            if request.apply_highpass_filter is not None
            else False,
            set_sample_rate_16k=request.set_sample_rate_16k
            if request.set_sample_rate_16k is not None
            else settings["default_sample_rate_16k"],
        )
        return job
    except ValueError as e:
        raise ValidationError(f"Invalid request data: {str(e)}")
    except Exception as e:
        raise JobCreationError(f"Failed to create pipeline job: {str(e)}")


async def _schedule_pipeline_execution(
    job: PipelineJob, background_tasks: BackgroundTasks
) -> None:
    """
    Schedule pipeline execution in background.

    Args:
        job: Pipeline job to execute
        background_tasks: FastAPI background tasks

    Raises:
        RedisConnectionError: If Redis connection fails
        JobCreationError: If scheduling fails
    """
    try:
        redis_store = get_store()
        redis_store.save_job(job)
        logger.info(f"Pipeline job {job.id} saved to Redis")

        from services.pipeline_background import execute_pipeline_background

        background_tasks.add_task(execute_pipeline_background, job.id)
        logger.info(f"Background task scheduled for job {job.id}")
    except ConnectionError as e:
        raise RedisConnectionError(f"Failed to connect to Redis: {str(e)}")
    except Exception as e:
        raise JobCreationError(f"Failed to schedule pipeline execution: {str(e)}")


async def _build_pipeline_response(job: PipelineJob) -> PipelineResponse:
    """
    Build pipeline response from job.

    Args:
        job: Pipeline job

    Returns:
        Pipeline response
    """
    return PipelineResponse(
        job_id=job.id,
        status=job.status,
        message="Pipeline iniciado com sucesso. Use /jobs/{job_id} para acompanhar.",
        youtube_url=job.youtube_url,
        overall_progress=0.0,
    )


@router.post("/process", response_model=PipelineResponse)
async def process_youtube_video(
    request: PipelineRequest, background_tasks: BackgroundTasks
) -> PipelineResponse:
    """
    Inicia processamento completo de um vídeo do YouTube.

    Pipeline:
    1. Download do vídeo (video-downloader)
    2. Normalização de áudio (audio-normalization)
    3. Transcrição (audio-transcriber)

    Retorna imediatamente com job_id para consulta de status.

    Args:
        request: Pipeline request
        background_tasks: FastAPI background tasks

    Returns:
        Pipeline response with job_id

    Raises:
        HTTPException: If validation fails or job creation fails
    """
    try:
        job = await _create_pipeline_job(request)
        await _schedule_pipeline_execution(job, background_tasks)
        return await _build_pipeline_response(job)
    except ValidationError as e:
        logger.warning(f"Validation failed: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except RedisConnectionError as e:
        logger.error(f"Redis connection failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
    except JobCreationError as e:
        logger.error(f"Failed to create job: {e}")
        raise HTTPException(status_code=500, detail=str(e))
