"""
Job query routes for the orchestrator service.
"""
import json
import asyncio
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

from common.log_utils import get_logger
from domain.models import JobListResponse, PipelineStatus, PipelineStatusResponse
from modules.redis_store import get_store
from core.config import get_settings
from domain.builders import StageResponseBuilder

logger = get_logger(__name__)
router = APIRouter(prefix="", tags=["Jobs"])
settings = get_settings()


def _get_redis_store():
    return get_store()


@router.get(
    "/jobs",
    summary="Listar jobs",
    description="Lista jobs recentes da pipeline com progresso resumido para polling e dashboards.",
    response_model=JobListResponse,
    responses={500: {"description": "Internal server error"}},
)
async def list_jobs(
    limit: int = Query(50, ge=1, le=200, description="Quantidade máxima de jobs retornados.", examples=[50, 100]),
    redis_store=Depends(_get_redis_store),
):
    """Lista jobs recentes da pipeline com status e progresso."""
    try:
        job_ids = redis_store.list_jobs(limit=limit)

        jobs = []
        for job_id in job_ids:
            job = redis_store.get_job(job_id)
            if job:
                jobs.append({
                    "job_id": job.id,
                    "youtube_url": job.youtube_url,
                    "status": job.status.value,
                    "progress": job.overall_progress,
                    "created_at": job.created_at,
                    "updated_at": job.updated_at,
                })

        return {"total": len(jobs), "jobs": jobs}

    except Exception as e:
        logger.error(f"Failed to list jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar jobs: {str(e)}")


@router.get(
    "/jobs/{job_id}",
    summary="Obter status do job",
    description="Retorna o estado detalhado do pipeline, incluindo progresso por estágio e artefatos já produzidos.",
    response_model=PipelineStatusResponse,
    responses={404: {"description": "Job not found"}, 500: {"description": "Internal server error"}},
)
async def get_job_status(
    job_id: str = Path(..., description="ID do job para consulta de status.", examples=["pipe_abc123"]),
    redis_store=Depends(_get_redis_store),
):
    """Retorna o status detalhado de um job da pipeline, incluindo todos os estágios."""
    try:
        job = redis_store.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} nao encontrado")

        stages = StageResponseBuilder.build_all_stages(job)

        segments_as_dicts = None
        if job.transcription_segments:
            segments_as_dicts = [
                {
                    "text": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                    "duration": seg.duration,
                }
                for seg in job.transcription_segments
            ]

        return PipelineStatusResponse(
            job_id=job.id,
            youtube_url=job.youtube_url,
            status=job.status,
            overall_progress=job.overall_progress,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
            stages=stages,
            transcription_text=job.transcription_text,
            transcription_segments=segments_as_dicts,
            transcription_file=job.transcription_file,
            audio_file=job.audio_file,
            error_message=job.error_message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao consultar job: {str(e)}")


@router.get(
    "/jobs/{job_id}/wait",
    summary="Aguardar conclusao do job",
    description="Mantém a conexão aberta até o pipeline terminar, falhar ou atingir o timeout informado.",
    response_model=PipelineStatusResponse,
    responses={404: {"description": "Job not found"}, 408: {"description": "Timeout waiting for job"}, 500: {"description": "Internal server error"}},
)
async def wait_for_job_completion(
    job_id: str = Path(..., description="ID do job para aguardar conclusão.", examples=["pipe_abc123"]),
    timeout: int = Query(1800, ge=1, le=7200, description="Tempo máximo de espera em segundos.", examples=[300, 1800]),
    redis_store=Depends(_get_redis_store),
):
    """Mantém a conexão aberta até o job concluir, falhar ou atingir timeout."""
    start_time = now_brazil()
    max_wait = timedelta(seconds=timeout)
    poll_interval = 5

    logger.info(f"Client waiting for job {job_id} completion (timeout: {timeout}s)")

    try:
        while now_brazil() - start_time < max_wait:
            job = redis_store.get_job(job_id)

            if not job:
                raise HTTPException(status_code=404, detail=f"Job {job_id} nao encontrado")

            if job.status in [PipelineStatus.COMPLETED, PipelineStatus.FAILED, PipelineStatus.CANCELLED]:
                elapsed = (now_brazil() - start_time).total_seconds()
                logger.info(f"Job {job_id} finished with status {job.status.value} after {elapsed:.1f}s")

                stages = StageResponseBuilder.build_all_stages(job)

                segments_as_dicts = None
                if job.transcription_segments:
                    segments_as_dicts = [
                        {
                            "text": seg.text,
                            "start": seg.start,
                            "end": seg.end,
                            "duration": seg.duration,
                        }
                        for seg in job.transcription_segments
                    ]

                return PipelineStatusResponse(
                    job_id=job.id,
                    youtube_url=job.youtube_url,
                    status=job.status,
                    overall_progress=job.overall_progress,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                    completed_at=job.completed_at,
                    stages=stages,
                    transcription_text=job.transcription_text,
                    transcription_segments=segments_as_dicts,
                    transcription_file=job.transcription_file,
                    audio_file=job.audio_file,
                    error_message=job.error_message,
                )

            logger.debug(f"Job {job_id} still processing: {job.status.value} ({job.overall_progress:.1f}%)")
            await asyncio.sleep(poll_interval)

        elapsed = (now_brazil() - start_time).total_seconds()
        logger.warning(f"Timeout waiting for job {job_id} after {elapsed:.1f}s")
        raise HTTPException(
            status_code=408,
            detail=f"Timeout aguardando conclusao do job apos {timeout}s. Use GET /jobs/{job_id} para verificar status atual.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error waiting for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao aguardar job: {str(e)}")


@router.get(
    "/jobs/{job_id}/stream",
    summary="Transmitir progresso do job",
    description=(
        "Abre um stream SSE (`text/event-stream`) com eventos `connected`, `progress`, `completed`, `error` e `timeout`. "
        "Use quando precisar acompanhar o progresso do pipeline em tempo real."
    ),
    responses={
        200: {
            "description": "SSE stream with real-time pipeline events",
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string", "example": "event: progress\\ndata: {\"job_id\": \"abc123\", \"status\": \"downloading\", \"progress\": 33.3}\\n\\n"}
                }
            },
        },
        404: {"description": "Job not found"},
    },
)
async def stream_job_progress(
    job_id: str = Path(..., description="ID do job para streaming de progresso.", examples=["pipe_abc123"]),
    timeout: int = Query(600, ge=1, le=7200, description="Timeout do stream em segundos.", examples=[600, 1200]),
    redis_store=Depends(_get_redis_store),
):
    """Abre um stream SSE para acompanhar o progresso do job em tempo real."""
    async def event_generator():
        start_time = now_brazil()
        max_wait = timedelta(seconds=timeout)
        poll_interval = 1
        last_progress = -1

        logger.info(f"Starting SSE stream for job {job_id}")

        try:
            yield f"event: connected\ndata: {json.dumps({'message': 'Conectado ao stream', 'job_id': job_id})}\n\n"

            while now_brazil() - start_time < max_wait:
                job = redis_store.get_job(job_id)

                if not job:
                    yield f"event: error\ndata: {json.dumps({'error': 'Job nao encontrado', 'job_id': job_id})}\n\n"
                    break

                if job.overall_progress != last_progress:
                    current_stage = job.get_current_stage()
                    stage_name = current_stage.name if current_stage else "waiting"

                    progress_data = {
                        "job_id": job.id,
                        "status": job.status.value,
                        "progress": job.overall_progress,
                        "stage": stage_name,
                        "stages": {
                            "download": job.download_stage.progress,
                            "normalization": job.normalization_stage.progress,
                            "transcription": job.transcription_stage.progress,
                        },
                    }

                    yield f"event: progress\ndata: {json.dumps(progress_data)}\n\n"
                    last_progress = job.overall_progress

                if job.status == PipelineStatus.COMPLETED:
                    completed_data = {
                        "job_id": job.id,
                        "status": "completed",
                        "progress": 100.0,
                        "message": "Pipeline concluido com sucesso!",
                        "transcription_file": job.transcription_file,
                        "audio_file": job.audio_file,
                        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    }
                    yield f"event: completed\ndata: {json.dumps(completed_data)}\n\n"
                    logger.info(f"Job {job_id} completed - closing SSE stream")
                    break

                elif job.status in [PipelineStatus.FAILED, PipelineStatus.CANCELLED]:
                    error_data = {
                        "job_id": job.id,
                        "status": job.status.value,
                        "error": job.error_message or "Job falhou",
                        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    }
                    yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
                    logger.warning(f"Job {job_id} failed - closing SSE stream")
                    break

                await asyncio.sleep(poll_interval)

            if now_brazil() - start_time >= max_wait:
                timeout_data = {
                    "job_id": job_id,
                    "error": f"Timeout apos {timeout}s",
                    "message": f"Use GET /jobs/{job_id} para verificar status",
                }
                yield f"event: timeout\ndata: {json.dumps(timeout_data)}\n\n"
                logger.warning(f"SSE stream timeout for job {job_id}")

        except Exception as e:
            logger.error(f"Error in SSE stream for job {job_id}: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )