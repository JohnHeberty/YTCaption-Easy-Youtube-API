"""
API principal do orquestrador
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from datetime import datetime
from typing import Optional

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
            remove_noise=request.remove_noise if request.remove_noise is not None else settings["default_remove_noise"],
            convert_to_mono=request.convert_to_mono if request.convert_to_mono is not None else settings["default_convert_mono"],
            sample_rate_16k=request.sample_rate_16k if request.sample_rate_16k is not None else settings["default_sample_rate_16k"]
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
            transcription_file=job.transcription_file,
            audio_file=job.audio_file,
            error_message=job.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao consultar job: {str(e)}")


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
                "poll_interval": settings["poll_interval"],
                "max_poll_attempts": settings["max_poll_attempts"]
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter estatísticas: {str(e)}")


@app.post("/admin/cleanup", tags=["Admin"])
async def cleanup_old_jobs(max_age_hours: int = None):
    """Remove jobs antigos do Redis"""
    try:
        removed = redis_store.cleanup_old_jobs(max_age_hours)
        
        return {
            "message": "Cleanup executado com sucesso",
            "jobs_removed": removed
        }
        
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao fazer cleanup: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings["app_host"],
        port=settings["app_port"],
        reload=settings["debug"],
        workers=settings["workers"] if not settings["debug"] else 1
    )
