"""
Audio Normalization Service - Main Application.

Serviço refatorado seguindo princípios SOLID e PYTHONIC.
- Responsabilidades separadas em serviços especializados
- Try/except específicos ao invés de blocos massivos
- Type hints em todo código público
- Sem datetime.now() - usando now_brazil()
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

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

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Form, Query, Depends, Path as PathParam
from fastapi.responses import FileResponse, JSONResponse

from common.fastapi_utils import create_service_app, create_api_key_dependency
from common.log_utils import setup_structured_logging, get_logger
from common.health_utils import ServiceHealthChecker

from .core.models import (
    AudioNormJob,
    AdminStatsResponse,
    CleanupResponse,
    DeleteJobResponse,
    HeartbeatResponse,
    HealthResponse,
    Job,
    QueueInfoResponse,
    RootResponse,
)
from common.job_utils.models import JobStatus
from .core.config import get_settings
from .core.validators import JobIdValidator, ValidationError
from .core.constants import FILE_CONSTANTS, JOB_CONSTANTS
from .infrastructure.redis_store import AudioNormJobStore
from .infrastructure.dependencies import (
    job_store,
    audio_processor,
    get_upload_dir,
    get_settings_dep,
)
from .services.audio_processor import AudioProcessor
from .services.job_service import (
    JobCreationService,
    JobSubmissionService,
    JobRetrievalService,
)
# Configuração inicial
settings = get_settings()
verify_api_key = create_api_key_dependency(api_key=settings.get('api_key'))
setup_structured_logging(
    service_name="audio-normalization",
    log_level=settings['log_level'],
    log_dir=settings['log_dir'],
    json_format=(settings.get('log_format', 'json') == 'json')
)
logger = get_logger(__name__)

store = job_store()


@asynccontextmanager
async def lifespan(app):
    store = job_store()
    await store.start_cleanup_task()
    logger.info("Audio Normalization Service iniciado com sucesso")
    yield
    await store.stop_cleanup_task()
    logger.info("Audio Normalization Service parado graciosamente")


app = create_service_app(
    service_name="audio-normalization",
    title="Audio Normalization Service",
    description="Microserviço para normalização de áudio com cache de 24h",
    version="2.0.0",
    settings=settings,
    lifespan=lifespan,
    body_size_mb=settings.get("max_file_size_mb"),
    dependencies=[Depends(verify_api_key)],
)

# ============================================================================
# ROUTES
# ============================================================================

@app.get(
    "/",
    summary="Service info",
    description="Retorna a visão geral do serviço e os endpoints principais para integração.",
    response_model=RootResponse,
)
async def root() -> dict:
    """Endpoint raiz - Informações do serviço."""
    return {
        "service": "Audio Normalization Service",
        "version": "2.0.0",
        "status": "running",
        "description": "Microserviço para normalização de áudio com cache de 24h",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "jobs": {
                "create": "POST /jobs",
                "get": "GET /jobs/{job_id}",
                "list": "GET /jobs",
                "download": "GET /jobs/{job_id}/download",
                "delete": "DELETE /jobs/{job_id}",
            },
            "admin": {
                "stats": "GET /admin/stats",
                "queue": "GET /admin/queue",
                "cleanup": "POST /admin/cleanup",
            }
        }
    }


@app.post("/jobs", response_model=Job)
async def create_audio_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(
        ...,
        description="Arquivo de áudio/vídeo para normalização. Formatos comuns: mp3, wav, m4a, webm, mp4.",
    ),
    remove_noise: Optional[str] = Form(
        default="false",
        description="Ativa redução de ruído. Aceita: true, false, 1, 0, yes, no, on, off.",
        examples=["true", "false", "1", "0"],
    ),
    convert_to_mono: Optional[str] = Form(
        default="false",
        description="Converte áudio para mono. Aceita: true, false, 1, 0, yes, no, on, off.",
        examples=["true", "false"],
    ),
    apply_highpass_filter: Optional[str] = Form(
        default="false",
        description="Aplica filtro passa-alta. Aceita: true, false, 1, 0, yes, no, on, off.",
        examples=["false", "true"],
    ),
    set_sample_rate_16k: Optional[str] = Form(
        default="false",
        description="Define sample rate para 16kHz. Aceita: true, false, 1, 0, yes, no, on, off.",
        examples=["true", "false"],
    ),
    isolate_vocals: Optional[str] = Form(
        default="false",
        description="Ativa isolamento de voz. Aceita: true, false, 1, 0, yes, no, on, off.",
        examples=["false", "true"],
    ),
    store: AudioNormJobStore = Depends(job_store),
    processor: AudioProcessor = Depends(audio_processor),
) -> Job:
    """
    Cria um novo job de processamento de áudio.

    Aceita QUALQUER formato de áudio como entrada e SEMPRE retorna .webm.
    """
    creation_service = JobCreationService(
        job_store=store,
        upload_dir=get_upload_dir(),
        max_file_size_mb=get_settings_dep()['max_file_size_mb']
    )
    submission_service = JobSubmissionService(job_store=store)

    # 1. Validação do arquivo
    try:
        validation_result = await creation_service.validate_input(
            file,
            remove_noise=remove_noise,
            convert_to_mono=convert_to_mono,
            apply_highpass_filter=apply_highpass_filter,
            set_sample_rate_16k=set_sample_rate_16k,
            isolate_vocals=isolate_vocals
        )
    except ValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e.detail))
    except Exception as e:
        logger.error(f"Erro na validação: {e}")
        raise HTTPException(status_code=400, detail=f"Erro na validação: {e}")

    # 2. Criação da entidade Job
    try:
        new_job = creation_service.create_job_entity(
            filename=validation_result.original_filename,
            processing_params=validation_result.processing_params
        )
    except Exception as e:
        logger.error(f"Erro ao criar job: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar job: {e}")

    # 3. Verifica cache
    try:
        existing_job = submission_service.check_existing_job(new_job)
        if existing_job:
            return existing_job
    except Exception as e:
        logger.warning(f"Erro ao verificar cache: {e}")
        # Continua mesmo se falhar

    # 4. Salva arquivo
    try:
        file_path = creation_service.save_file(
            new_job,
            validation_result.content,
            validation_result.extension
        )
        new_job.input_file = str(file_path)
        new_job.file_size_input = file_path.stat().st_size
    except ValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e.detail))
    except Exception as e:
        logger.error(f"Erro ao salvar arquivo: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao salvar arquivo: {e}")

    # 5. Salva job e submete
    try:
        store.save_job(new_job)
        await submission_service.submit_with_fallback(new_job, processor)
        logger.info(f"Job {new_job.id} criado e submetido")
    except RedisError as e:
        # Limpa arquivo se falhou
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=503, detail=f"Erro ao salvar job: {e}")
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        logger.error(f"Erro ao submeter job: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao submeter job: {e}")

    return new_job


@app.get("/jobs/{job_id}", response_model=Job)
async def get_job_status(
    job_id: str = PathParam(..., description="ID do job a consultar.", examples=["an_abc123def456"]),
    store: AudioNormJobStore = Depends(job_store),
) -> Job:
    """Consulta status de um job."""
    # Valida job_id
    try:
        job_id = JobIdValidator.validate(job_id)
    except ValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e.detail))

    retrieval_service = JobRetrievalService(job_store=store)

    # Busca job
    try:
        job = retrieval_service.get_job(job_id)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job não encontrado: {job_id}")
    except Exception as e:
        logger.error(f"Erro ao buscar job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar job: {e}")

    # Verifica expiração
    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expirado")

    return job


@app.get("/jobs/{job_id}/download")
async def download_file(
    job_id: str = PathParam(..., description="ID do job para download do resultado.", examples=["an_abc123def456"]),
    store: AudioNormJobStore = Depends(job_store),
) -> FileResponse:
    """Faz download do arquivo processado."""
    # Valida job_id
    try:
        job_id = JobIdValidator.validate(job_id)
    except ValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e.detail))

    retrieval_service = JobRetrievalService(job_store=store)

    # Busca job
    try:
        job = retrieval_service.get_job_with_expiration_check(job_id)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    except JobExpiredError:
        raise HTTPException(status_code=410, detail="Job expirado")

    # Verifica se está completo
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=425,
            detail=f"Processamento não pronto. Status: {job.status}"
        )

    # Verifica arquivo de saída
    if not job.output_file:
        raise HTTPException(status_code=404, detail="Arquivo de saída não definido")

    file_path = Path(job.output_file)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    return FileResponse(
        path=file_path,
        filename=f"normalized_{job_id}.webm",
        media_type='application/octet-stream'
    )


@app.get("/jobs", response_model=List[Job])
async def list_jobs(
    limit: int = Query(
        default=20,
        ge=1,
        le=200,
        description="Quantidade máxima de jobs retornados.",
        examples=[20, 50],
    ),
    store: AudioNormJobStore = Depends(job_store),
) -> List[Job]:
    """Lista jobs recentes."""
    retrieval_service = JobRetrievalService(job_store=store)

    try:
        return retrieval_service.list_recent_jobs(limit)
    except Exception as e:
        logger.error(f"Erro ao listar jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar jobs: {e}")


@app.delete("/jobs/{job_id}", response_model=DeleteJobResponse)
async def delete_job(
    job_id: str = PathParam(..., description="ID do job a remover.", examples=["an_abc123def456"]),
    store: AudioNormJobStore = Depends(job_store),
) -> DeleteJobResponse:
    """Remove job e arquivos associados."""
    # Valida job_id
    try:
        job_id = JobIdValidator.validate(job_id)
    except ValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e.detail))

    retrieval_service = JobRetrievalService(job_store=store)

    # Busca job
    try:
        job = retrieval_service.get_job(job_id)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    # Remove arquivos
    files_deleted = 0
    try:
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
    except Exception as e:
        logger.warning(f"Erro ao remover arquivos: {e}")

    # Remove do Redis
    try:
        store.delete_job(job_id)
        logger.info(f"🗑️ Job {job_id} removido do Redis")
    except Exception as e:
        logger.error(f"Erro ao remover job do Redis: {e}")

    return {
        "message": "Job removido com sucesso",
        "job_id": job_id,
        "files_deleted": files_deleted
    }


@app.post("/jobs/{job_id}/heartbeat")
async def update_heartbeat(
    job_id: str = PathParam(..., description="ID do job para atualização de heartbeat."),
    store: AudioNormJobStore = Depends(job_store),
) -> HeartbeatResponse:
    """Atualiza heartbeat do job."""
    # Valida job_id
    try:
        job_id = JobIdValidator.validate(job_id)
    except ValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e.detail))

    retrieval_service = JobRetrievalService(job_store=store)

    try:
        job = retrieval_service.get_job(job_id)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    # Atualiza heartbeat
    job.update_heartbeat()
    store.update_job(job)

    logger.debug(f"💓 Heartbeat atualizado: {job_id}")

    return {
        "id": job_id,
        "status": "ok",
        "last_heartbeat": job.last_heartbeat
    }


# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.get(
    "/admin/stats",
    summary="System stats",
    description="Retorna estatísticas agregadas de jobs e métricas de cache local do serviço.",
    response_model=AdminStatsResponse,
)
async def get_stats(
    store: AudioNormJobStore = Depends(job_store),
) -> AdminStatsResponse:
    """Estatísticas do sistema."""
    try:
        stats = store.get_stats()
    except Exception as e:
        logger.error(f"Erro ao obter stats: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter estatísticas: {e}")

    # Adiciona info de cache
    upload_path = Path(settings.get('upload_dir', './uploads'))
    processed_path = Path(settings.get('processed_dir', './processed'))

    total_files = 0
    total_size = 0

    for path in [upload_path, processed_path]:
        if path.exists():
            try:
                files = list(path.iterdir())
                total_files += len([f for f in files if f.is_file()])
                total_size += sum(f.stat().st_size for f in files if f.is_file())
            except Exception as e:
                logger.warning(f"Erro ao ler diretório {path}: {e}")

    stats["cache"] = {
        "files_count": total_files,
        "total_size_mb": round(total_size / (1024 * 1024), 2)
    }

    return stats


@app.get(
    "/admin/queue",
    summary="Queue info",
    description="Retorna o estado atual da fila e do processamento assíncrono de jobs.",
    response_model=QueueInfoResponse,
)
async def get_queue_info(
    store: AudioNormJobStore = Depends(job_store),
) -> QueueInfoResponse:
    """Informações da fila de jobs."""
    try:
        queue_info = await store.get_queue_info()
        return {"status": "success", "queue": queue_info}
    except Exception as e:
        logger.error(f"Erro ao obter queue info: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter fila: {e}")


@app.post(
    "/admin/cleanup",
    summary="Manual cleanup",
    description=(
        "Executa limpeza manual do serviço. Use `deep=true` para incluir limpeza profunda "
        "do Redis e artefatos relacionados."
    ),
    response_model=CleanupResponse,
)
async def manual_cleanup(
    deep: bool = Query(
        default=False,
        description="Quando true, executa limpeza profunda (inclui flush completo do Redis).",
        examples=[False, True],
    ),
    store: AudioNormJobStore = Depends(job_store),
) -> CleanupResponse:
    """Limpeza do sistema."""
    from .services.cleanup_service import CleanupService

    cleanup_service = CleanupService(store)

    try:
        if deep:
            result = await cleanup_service.perform_deep_cleanup()
        else:
            result = await cleanup_service.perform_basic_cleanup()

        logger.info(f"✅ Limpeza {'profunda' if deep else 'básica'} concluída")
        return result

    except Exception as e:
        logger.error(f"❌ Erro na limpeza: {e}")
        raise HTTPException(status_code=500, detail=f"Erro na limpeza: {e}")


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get(
    "/health",
    summary="Health check",
    description=(
        "Executa verificação profunda do serviço, incluindo Redis, espaço em disco "
        "e disponibilidade do FFmpeg."
    ),
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Service unhealthy"}},
)
async def health_check(
    store: AudioNormJobStore = Depends(job_store),
) -> JSONResponse:
    """Health check profundo usando ServiceHealthChecker compartilhado."""
    checker = ServiceHealthChecker("audio-normalization", version=settings.app_version)

    checker.add_check("redis", lambda: ServiceHealthChecker.check_redis(store.redis))
    checker.add_check("disk", lambda: _check_disk_space(settings['temp_dir']))
    checker.add_check("ffmpeg", ServiceHealthChecker.check_ffmpeg)

    result = await checker.check_all()

    is_healthy = result["status"] == "healthy"
    status_code = 200 if is_healthy else 503

    return JSONResponse(content=result, status_code=status_code)


def _check_disk_space(path: str) -> dict:
    import shutil
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        stat = shutil.disk_usage(path)
        free_gb = stat.free / (1024 ** 3)
        percent_free = (stat.free / stat.total) * 100
        if percent_free <= 5:
            status = "error"
        elif percent_free <= 10:
            status = "warning"
        else:
            status = "ok"
        return {
            "status": status,
            "free_gb": round(free_gb, 2),
            "percent_free": round(percent_free, 2),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/metrics")
async def prometheus_metrics(
    store: AudioNormJobStore = Depends(job_store),
) -> JSONResponse:
    """Prometheus metrics endpoint."""
    from fastapi.responses import Response

    svc = "audio_normalization"

    try:
        stats = store.get_stats()
    except Exception as e:
        logger.warning(f"Erro ao obter stats: {e}")
        stats = {"by_status": {}, "total_jobs": 0}

    by_status = stats.get("by_status", {})
    total = stats.get("total_jobs", 0)

    lines = [
        f"# HELP {svc}_jobs_total Jobs in Redis store by status",
        f"# TYPE {svc}_jobs_total gauge",
    ]
    for status_name, count in by_status.items():
        lines.append(f'{svc}_jobs_total{{status="{status_name}"}} {count}')
    lines += [
        f"# HELP {svc}_jobs_store_total Total jobs in Redis store",
        f"# TYPE {svc}_jobs_store_total gauge",
        f"{svc}_jobs_store_total {total}",
    ]

    return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
