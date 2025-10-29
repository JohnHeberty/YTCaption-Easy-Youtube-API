"""
API principal do orquestrador
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

from modules.models import (
    PipelineRequest,
    PipelineResponse,
    PipelineStatusResponse,
    PipelineJob,
    PipelineStatus,
    HealthResponse
)
from modules.orchestrator import PipelineOrchestrator
from modules.redis_store import get_store
from modules.config import get_orchestrator_settings

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variáveis globais
orchestrator: Optional[PipelineOrchestrator] = None
redis_store = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle da aplicação"""
    global orchestrator, redis_store
    
    # Startup
    logger.info("Starting orchestrator API...")
    
    try:
        redis_store = get_store()
        orchestrator = PipelineOrchestrator()
        logger.info("Orchestrator initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down orchestrator API...")


# Configuração da aplicação
settings = get_orchestrator_settings()

app = FastAPI(
    title="YouTube Caption Orchestrator API",
    description="API orquestradora para processar vídeos do YouTube: download → normalização → transcrição",
    version=settings["app_version"],
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
async def root():
    """Endpoint raiz"""
    return {
        "service": "YouTube Caption Orchestrator",
        "version": settings["app_version"],
        "status": "running",
        "endpoints": {
            "health": "/health",
            "process": "/process (POST)",
            "job_status": "/jobs/{job_id} (GET)",
            "list_jobs": "/jobs (GET)",
            "docs": "/docs"
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Verifica saúde do orquestrador e microserviços"""
    try:
        # Verifica Redis
        redis_ok = redis_store.ping() if redis_store else False
        
        # Verifica microserviços
        microservices_status = {}
        if orchestrator:
            microservices_status = await orchestrator.check_services_health()
        
        # Status geral
        all_healthy = redis_ok and all(
            status == "healthy" for status in microservices_status.values()
        )
        
        return HealthResponse(
            status="healthy" if all_healthy else "degraded",
            service="orchestrator",
            version=settings["app_version"],
            timestamp=datetime.now(),
            microservices=microservices_status
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")


@app.post("/process", response_model=PipelineResponse, tags=["Pipeline"])
async def process_youtube_video(
    request: PipelineRequest,
    background_tasks: BackgroundTasks
):
    """
    Inicia processamento completo de um vídeo do YouTube.
    
    Pipeline:
    1. Download do vídeo (video-downloader)
    2. Normalização de áudio (audio-normalization)
    3. Transcrição (audio-transcriber)
    
    Retorna imediatamente com job_id para consulta de status.
    """
    try:
        # Cria job
        job = PipelineJob.create_new(
            youtube_url=request.youtube_url,
            language=request.language or settings["default_language"],
            language_out=request.language_out,  # Tradução opcional
            remove_noise=request.remove_noise if request.remove_noise is not None else settings["default_remove_noise"],
            convert_to_mono=request.convert_to_mono if request.convert_to_mono is not None else settings["default_convert_mono"],
            apply_highpass_filter=request.apply_highpass_filter if request.apply_highpass_filter is not None else False,
            set_sample_rate_16k=request.set_sample_rate_16k if request.set_sample_rate_16k is not None else settings["default_sample_rate_16k"],
            isolate_vocals=request.isolate_vocals if request.isolate_vocals is not None else False
        )
        
        # Salva job
        redis_store.save_job(job)
        
        # Agenda execução em background
        background_tasks.add_task(execute_pipeline_background, job.id)
        
        logger.info(f"Pipeline job {job.id} created for URL: {request.youtube_url}")
        
        return PipelineResponse(
            job_id=job.id,
            status=job.status,
            message="Pipeline iniciado com sucesso. Use /jobs/{job_id} para acompanhar o progresso.",
            youtube_url=job.youtube_url,
            overall_progress=0.0
        )
        
    except Exception as e:
        logger.error(f"Failed to create pipeline job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar job: {str(e)}")

async def execute_pipeline_background(job_id: str):
    """Executa pipeline em background"""
    try:
        logger.info(f"Starting background pipeline for job {job_id}")
        
        # Recupera job
        job = redis_store.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        # Executa pipeline
        job = await orchestrator.execute_pipeline(job)
        
        # Salva resultado
        redis_store.save_job(job)
        
        logger.info(f"Pipeline for job {job_id} finished with status: {job.status}")
        
    except Exception as e:
        logger.error(f"Pipeline execution failed for job {job_id}: {str(e)}")
        
        # Tenta recuperar e marcar como falho
        try:
            job = redis_store.get_job(job_id)
            if job:
                job.mark_as_failed(str(e))
                redis_store.save_job(job)
        except:
            pass

@app.get("/jobs", tags=["Jobs"])
async def list_jobs(limit: int = 50):
    """
    Lista jobs recentes do pipeline.
    
    Retorna IDs dos últimos jobs criados (mais recentes primeiro).
    """
    try:
        job_ids = redis_store.list_jobs(limit=limit)
        
        # Busca informações básicas de cada job
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
                    "updated_at": job.updated_at
                })
        
        return {
            "total": len(jobs),
            "jobs": jobs
        }
        
    except Exception as e:
        logger.error(f"Failed to list jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar jobs: {str(e)}")

@app.get("/jobs/{job_id}", response_model=PipelineStatusResponse, tags=["Jobs"])
async def get_job_status(job_id: str):
    """
    Consulta status detalhado de um job do pipeline.
    
    Retorna informações sobre cada estágio (download, normalização, transcrição)
    e o progresso geral.
    """
    try:
        job = redis_store.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} não encontrado")
        
        # Monta resposta com status dos estágios
        stages = {
            "download": {
                "status": job.download_stage.status.value,
                "job_id": job.download_stage.job_id,
                "progress": job.download_stage.progress,
                "started_at": job.download_stage.started_at,
                "completed_at": job.download_stage.completed_at,
                "error": job.download_stage.error_message
            },
            "normalization": {
                "status": job.normalization_stage.status.value,
                "job_id": job.normalization_stage.job_id,
                "progress": job.normalization_stage.progress,
                "started_at": job.normalization_stage.started_at,
                "completed_at": job.normalization_stage.completed_at,
                "error": job.normalization_stage.error_message
            },
            "transcription": {
                "status": job.transcription_stage.status.value,
                "job_id": job.transcription_stage.job_id,
                "progress": job.transcription_stage.progress,
                "started_at": job.transcription_stage.started_at,
                "completed_at": job.transcription_stage.completed_at,
                "error": job.transcription_stage.error_message
            }
        }
        
        # Converte TranscriptionSegment objects para dicts
        segments_as_dicts = None
        if job.transcription_segments:
            segments_as_dicts = [
                {
                    "text": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                    "duration": seg.duration
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
            error_message=job.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao consultar job: {str(e)}")

@app.get("/admin/stats", tags=["Admin"])
async def get_stats():
    """Retorna estatísticas do orquestrador"""
    try:
        stats = redis_store.get_stats()
        
        return {
            "orchestrator": {
                "version": settings["app_version"],
                "environment": settings["environment"]
            },
            "redis": stats,
            "settings": {
                "cache_ttl_hours": settings["cache_ttl_hours"],
                "job_timeout_minutes": settings["job_timeout_minutes"],
                "poll_interval_initial": settings["poll_interval_initial"],
                "poll_interval_max": settings["poll_interval_max"],
                "max_poll_attempts": settings["max_poll_attempts"]
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter estatísticas: {str(e)}")


@app.post("/admin/cleanup", tags=["Admin"])
async def cleanup_old_jobs(
    max_age_hours: int = None,
    deep: bool = False,
    remove_logs: bool = False
):
    """
    Remove jobs antigos do Redis.
    
    - max_age_hours: idade máxima dos jobs (None = usa default de 24h)
    - deep: se True, remove também arquivos de logs
    - remove_logs: se True, remove arquivos de log do diretório logs/
    """
    try:
        result = {
            "message": "Cleanup executado com sucesso",
            "jobs_removed": 0,
            "logs_cleaned": False
        }
        
        # Limpa jobs do Redis
        removed = redis_store.cleanup_old_jobs(max_age_hours)
        result["jobs_removed"] = removed
        
        # Deep cleanup: limpa logs se solicitado
        if deep or remove_logs:
            import shutil
            log_dir = Path(settings["log_dir"])
            if log_dir.exists():
                # Remove arquivos de log antigos
                for log_file in log_dir.glob("*.log*"):
                    try:
                        log_file.unlink()
                        logger.info(f"Removed log file: {log_file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove {log_file}: {e}")
                result["logs_cleaned"] = True
        
        return result
        
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao fazer cleanup: {str(e)}")


@app.post("/admin/factory-reset", tags=["Admin"])
async def factory_reset():
    """
    ⚠️ FACTORY RESET - Remove TUDO: todos os jobs do Redis, todos os logs,
    e requisita cleanup de TODOS os microserviços.
    Use com cuidado! Esta ação é irreversível.
    """
    try:
        result = {
            "message": "Factory reset executado em todos os serviços",
            "orchestrator": {
                "jobs_removed": 0,
                "logs_cleaned": False
            },
            "microservices": {},
            "warning": "Todos os dados foram removidos de todos os serviços"
        }
        
        # 1. Remove todos os jobs do Redis (age=0)
        removed = redis_store.cleanup_old_jobs(max_age_hours=0)
        result["orchestrator"]["jobs_removed"] = removed
        
        # 2. Limpa arquivos de log (sem remover diretório que está em uso)
        import shutil
        log_dir = Path(settings["log_dir"])
        if log_dir.exists():
            # Remove apenas os arquivos dentro do diretório, não o diretório em si
            for log_file in log_dir.glob("*.log*"):
                try:
                    log_file.unlink()
                    logger.info(f"Removed log file: {log_file}")
                except Exception as e:
                    logger.warning(f"Could not remove {log_file}: {e}")
            result["orchestrator"]["logs_cleaned"] = True
            logger.warning("Factory reset: All orchestrator logs cleaned")
        
        # 3. Chama cleanup de cada microserviço
        import httpx
        microservices = [
            ("video-downloader", orchestrator.video_client),
            ("audio-normalization", orchestrator.audio_client),
            ("audio-transcriber", orchestrator.transcription_client)
        ]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for service_name, service_client in microservices:
                try:
                    cleanup_url = f"{service_client.base_url}/admin/cleanup"
                    logger.info(f"Calling factory reset cleanup for {service_name}: {cleanup_url}")
                    
                    response = await client.post(
                        cleanup_url,
                        json={"deep": True}  # Deep cleanup nos microserviços
                    )
                    
                    if response.status_code == 200:
                        cleanup_data = response.json()
                        result["microservices"][service_name] = {
                            "status": "success",
                            "data": cleanup_data
                        }
                        logger.info(f"Factory reset cleanup successful for {service_name}")
                    else:
                        result["microservices"][service_name] = {
                            "status": "error",
                            "error": f"HTTP {response.status_code}"
                        }
                        logger.error(f"Factory reset cleanup failed for {service_name}: {response.status_code}")
                        
                except Exception as e:
                    result["microservices"][service_name] = {
                        "status": "error",
                        "error": str(e)
                    }
                    logger.error(f"Factory reset cleanup error for {service_name}: {str(e)}")
        
        logger.warning(f"Factory reset completed: orchestrator ({removed} jobs) + all microservices")
        return result
        
    except Exception as e:
        logger.error(f"Factory reset failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao fazer factory reset: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings["app_host"],
        port=settings["app_port"],
        reload=settings["debug"],
        workers=settings["workers"] if not settings["debug"] else 1
    )
