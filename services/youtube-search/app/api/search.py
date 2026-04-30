"""
Search API endpoints for YouTube Search service.

This module contains all search-related endpoints:
- Video info
- Channel info
- Playlist info
- Video search
- Related videos
- Shorts search
"""

from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Depends

from app.core.config import get_settings
from app.core.constants import SearchType, SearchLimits
from app.domain.models import Job
from app.infrastructure.redis_store import YouTubeSearchJobStore as RedisJobStore
from app.infrastructure.celery_tasks import youtube_search_task
from app.infrastructure.dependencies import get_job_store_override
from app.shared.exceptions import InvalidRequestError

from common.log_utils import get_logger
from app.core.validators import (
    ValidationError,
    MaxResultsValidator,
)

logger = get_logger(__name__)
router = APIRouter(tags=["Search"])

settings = get_settings()

def _validate_max_results(value: int) -> int:
    """
    Validate and normalize max_results parameter.

    Args:
        value: The max_results value to validate

    Returns:
        Normalized integer value

    Raises:
        InvalidRequestError: If value is invalid
    """
    try:
        return MaxResultsValidator.validate(value)
    except ValidationError as exc:
        raise InvalidRequestError(str(exc)) from exc

def _check_existing_job(job_id: str, store: RedisJobStore) -> Optional[Job]:
    """
    Check if job already exists and return appropriate response.

    Args:
        job_id: The job ID to check
        store: The job store instance

    Returns:
        Existing job if found and completed/processing, None otherwise
    """
    existing_job = store.get_job(job_id)

    if not existing_job:
        return None

    if existing_job.status.value == "completed":
        logger.info(f"Job {job_id} already completed (cache hit)")
        return existing_job
    elif existing_job.status.value == "processing":
        logger.info(f"Job {job_id} is processing")
        return existing_job

    return None

def _submit_celery_task(job: Job) -> None:
    """Submit job to Celery with configured timeout."""
    job_dict = job.model_dump(mode="json")

    youtube_search_task.apply_async(
        args=[job_dict],
        task_id=job.id,
        expires=settings["cache_ttl_hours"] * 3600,
    )

def _save_job(job: Job, store: RedisJobStore) -> None:
    """Save job to store."""
    store.save_job(job)

@router.post("/video-info", summary="Obter info do video", response_model=Job, responses={500: {"description": "Internal server error"}})
async def get_video_info(
    video_id: str = Query(
        ...,
        description="ID do vídeo no YouTube (11 caracteres) ou URL completa do vídeo.",
        examples=["dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
    ),
    store: RedisJobStore = Depends(get_job_store_override),
) -> Job:
    """Obtém informações de um vídeo do YouTube por ID ou URL."""
    try:
        logger.info(f"Request for video info: {video_id}")

        new_job = Job.create_new(
            search_type=SearchType.VIDEO_INFO,
            video_id=video_id,
            cache_ttl_hours=settings["cache_ttl_hours"],
        )

        existing = _check_existing_job(new_job.id, store)
        if existing:
            return existing

        _save_job(new_job, store)
        _submit_celery_task(new_job)

        logger.info(f"Job {new_job.id} created and submitted to Celery")
        return new_job

    except InvalidRequestError:
        raise
    except Exception as exc:
        logger.error(f"Error creating video info job: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/channel-info", summary="Obter info do canal", response_model=Job, responses={500: {"description": "Internal server error"}})
async def get_channel_info(
    channel_id: str = Query(
        ...,
        description="ID do canal no YouTube. Exemplo comum: inicia com UC.",
        examples=["UCuAXFkgsw1L7xaCfnd5JJOw"],
    ),
    include_videos: bool = Query(
        default=False,
        description="Quando true, inclui listagem de vídeos do canal no resultado.",
        examples=[False, True],
    ),
    store: RedisJobStore = Depends(get_job_store_override),
) -> Job:
    """Obtém informações de um canal do YouTube, opcionalmente incluindo seus vídeos."""
    try:
        logger.info(
            f"Request for channel info: {channel_id} (include_videos: {include_videos})"
        )

        new_job = Job.create_new(
            search_type=SearchType.CHANNEL_INFO,
            channel_id=channel_id,
            include_videos=include_videos,
            cache_ttl_hours=settings["cache_ttl_hours"],
        )

        existing = _check_existing_job(new_job.id, store)
        if existing:
            return existing

        _save_job(new_job, store)
        _submit_celery_task(new_job)

        logger.info(f"Job {new_job.id} created and submitted to Celery")
        return new_job

    except InvalidRequestError:
        raise
    except Exception as exc:
        logger.error(f"Error creating channel info job: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/playlist-info", summary="Obter info da playlist", response_model=Job, responses={500: {"description": "Internal server error"}})
async def get_playlist_info(
    playlist_id: str = Query(
        ...,
        description="ID da playlist no YouTube.",
        examples=["PLrAXtmRdnEQy6nuqo2XWY5vY3w8VYl2AB"],
    ),
    store: RedisJobStore = Depends(get_job_store_override),
) -> Job:
    """Obtém informações de uma playlist do YouTube por ID."""
    try:
        logger.info(f"Request for playlist info: {playlist_id}")

        new_job = Job.create_new(
            search_type=SearchType.PLAYLIST_INFO,
            playlist_id=playlist_id,
            cache_ttl_hours=settings["cache_ttl_hours"],
        )

        existing = _check_existing_job(new_job.id, store)
        if existing:
            return existing

        _save_job(new_job, store)
        _submit_celery_task(new_job)

        logger.info(f"Job {new_job.id} created and submitted to Celery")
        return new_job

    except InvalidRequestError:
        raise
    except Exception as exc:
        logger.error(f"Error creating playlist info job: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/videos", summary="Buscar videos", response_model=Job, responses={500: {"description": "Internal server error"}})
async def search_videos(
    query: str = Query(
        ...,
        description="Texto da busca por vídeos.",
        examples=["python tutorial", "lofi hip hop"],
    ),
    max_results: int = Query(
        default=SearchLimits.DEFAULT_RESULTS,
        ge=SearchLimits.MIN_RESULTS,
        le=SearchLimits.MAX_RESULTS,
        description="Quantidade máxima de resultados retornados.",
        examples=[10, 25, 50],
    ),
    store: RedisJobStore = Depends(get_job_store_override),
) -> Job:
    """Busca vídeos do YouTube a partir de um texto de consulta."""
    try:
        logger.info(f"Search videos request: '{query}' (max: {max_results})")

        validated_max = _validate_max_results(max_results)

        new_job = Job.create_new(
            search_type=SearchType.VIDEO,
            query=query,
            max_results=validated_max,
            cache_ttl_hours=settings["cache_ttl_hours"],
        )

        existing = _check_existing_job(new_job.id, store)
        if existing:
            return existing

        _save_job(new_job, store)
        _submit_celery_task(new_job)

        logger.info(f"Job {new_job.id} created and submitted to Celery")
        return new_job

    except InvalidRequestError:
        raise
    except Exception as exc:
        logger.error(f"Error creating video search job: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/related-videos", summary="Obter videos relacionados", response_model=Job, responses={500: {"description": "Internal server error"}})
async def get_related_videos(
    video_id: str = Query(
        ...,
        description="ID do vídeo base para encontrar relacionados.",
        examples=["dQw4w9WgXcQ"],
    ),
    max_results: int = Query(
        default=SearchLimits.DEFAULT_RESULTS,
        ge=SearchLimits.MIN_RESULTS,
        le=SearchLimits.MAX_RESULTS,
        description="Quantidade máxima de vídeos relacionados retornados.",
        examples=[10, 20],
    ),
    store: RedisJobStore = Depends(get_job_store_override),
) -> Job:
    """Busca vídeos relacionados a um vídeo base do YouTube."""
    try:
        logger.info(f"Request for related videos: {video_id} (max: {max_results})")

        validated_max = _validate_max_results(max_results)

        new_job = Job.create_new(
            search_type=SearchType.RELATED_VIDEOS,
            video_id=video_id,
            max_results=validated_max,
            cache_ttl_hours=settings["cache_ttl_hours"],
        )

        existing = _check_existing_job(new_job.id, store)
        if existing:
            return existing

        _save_job(new_job, store)
        _submit_celery_task(new_job)

        logger.info(f"Job {new_job.id} created and submitted to Celery")
        return new_job

    except InvalidRequestError:
        raise
    except Exception as exc:
        logger.error(f"Error creating related videos job: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/shorts", summary="Buscar shorts", response_model=Job, responses={500: {"description": "Internal server error"}})
async def search_shorts(
    query: str = Query(
        ...,
        description="Texto da busca para retornar apenas Shorts (até 60s).",
        examples=["receita rápida", "dicas de produtividade"],
    ),
    max_results: int = Query(
        default=SearchLimits.DEFAULT_RESULTS,
        ge=SearchLimits.MIN_RESULTS,
        le=SearchLimits.MAX_RESULTS,
        description="Quantidade máxima de Shorts retornados.",
        examples=[10, 30],
    ),
    store: RedisJobStore = Depends(get_job_store_override),
) -> Job:
    """Busca apenas Shorts do YouTube, limitados a vídeos com até 60 segundos."""
    try:
        logger.info(f"Search shorts request: '{query}' (max: {max_results})")

        validated_max = _validate_max_results(max_results)

        new_job = Job.create_new(
            search_type=SearchType.SHORTS,
            query=query,
            max_results=validated_max,
            cache_ttl_hours=settings["cache_ttl_hours"],
        )

        existing = _check_existing_job(new_job.id, store)
        if existing:
            return existing

        _save_job(new_job, store)
        _submit_celery_task(new_job)

        logger.info(f"Job {new_job.id} created and submitted to Celery")
        return new_job

    except InvalidRequestError:
        raise
    except Exception as exc:
        logger.error(f"Error creating shorts search job: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
