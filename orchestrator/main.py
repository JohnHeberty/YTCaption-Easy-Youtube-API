"""
API principal do orquestrador
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import logging
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
import json
import asyncio

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
        orchestrator = PipelineOrchestrator(redis_store=redis_store)
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
            "process": "/process (POST) - Inicia novo pipeline",
            "job_status": "/jobs/{job_id} (GET) - Consulta status com progresso em tempo real",
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
        
        # Salva job inicial
        redis_store.save_job(job)
        logger.info(f"Pipeline job {job.id} created and saved to Redis")
        
        # Agenda execução em background
        background_tasks.add_task(execute_pipeline_background, job.id)
        logger.info(f"Background task scheduled for job {job.id}")
        
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
    logger.info(f"⚡ BACKGROUND TASK STARTED for job {job_id}")
    
    try:
        logger.info(f"Starting background pipeline for job {job_id}")
        
        # Recupera job
        job = redis_store.get_job(job_id)
        if not job:
            logger.error(f"❌ Job {job_id} not found in Redis!")
            return
        
        logger.info(f"✅ Job {job_id} retrieved from Redis, status: {job.status}")
        
        # Verifica se orchestrator está disponível
        if not orchestrator:
            logger.error(f"❌ Orchestrator not initialized!")
            job.mark_as_failed("Orchestrator not available")
            redis_store.save_job(job)
            return
        
        logger.info(f"🚀 Executing pipeline for job {job_id}...")
        
        # Executa pipeline
        job = await orchestrator.execute_pipeline(job)
        
        logger.info(f"✅ Pipeline execution finished for job {job_id}, status: {job.status}")
        
        # Salva resultado
        redis_store.save_job(job)
        
        logger.info(f"Pipeline for job {job_id} finished with status: {job.status}")
        
    except Exception as e:
        logger.error(f"❌ Pipeline execution failed for job {job_id}: {str(e)}", exc_info=True)
        
        # Tenta recuperar e marcar como falho
        try:
            job = redis_store.get_job(job_id)
            if job:
                job.mark_as_failed(str(e))
                redis_store.save_job(job)
                logger.info(f"Job {job_id} marked as failed in Redis")
        except Exception as save_error:
            logger.error(f"Failed to save error state for job {job_id}: {save_error}")

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

@app.get("/jobs/{job_id}/wait", response_model=PipelineStatusResponse, tags=["Jobs"])
async def wait_for_job_completion(
    job_id: str,
    timeout: int = 1800  # 30 minutos padrão
):
    """
    🔄 **Aguarda a conclusão do job (long polling)**
    
    Este endpoint mantém a conexão aberta até que:
    - ✅ O job seja concluído com sucesso
    - ❌ O job falhe
    - ⏱️ O timeout seja atingido (padrão: 600s = 10min)
    
    **Parâmetros:**
    - `timeout`: Tempo máximo de espera em segundos (padrão: 600)
    
    **Exemplo:**
    ```
    GET /jobs/{job_id}/wait?timeout=300
    ```
    
    **Comportamento:**
    - Verifica o status a cada 2 segundos
    - Retorna imediatamente se o job já estiver concluído/falho
    - Mantém conexão com keep-alive
    
    **Retorna:** Status completo do pipeline quando finalizado
    """
    import asyncio
    from datetime import datetime, timedelta
    
    start_time = datetime.now()
    max_wait = timedelta(seconds=timeout)
    poll_interval = 5  # Verifica a cada 5 segundos
    
    logger.info(f"Client waiting for job {job_id} completion (timeout: {timeout}s)")
    
    try:
        while datetime.now() - start_time < max_wait:
            job = redis_store.get_job(job_id)
            
            if not job:
                raise HTTPException(status_code=404, detail=f"Job {job_id} não encontrado")
            
            # Verifica se job finalizou (sucesso ou erro)
            if job.status in [PipelineStatus.COMPLETED, PipelineStatus.FAILED, PipelineStatus.CANCELLED]:
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(f"Job {job_id} finished with status {job.status.value} after {elapsed:.1f}s")
                
                # Monta resposta completa
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
            
            # Job ainda processando - aguarda próximo poll
            logger.debug(f"Job {job_id} still processing: {job.status.value} ({job.overall_progress:.1f}%)")
            await asyncio.sleep(poll_interval)
        
        # Timeout atingido
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.warning(f"Timeout waiting for job {job_id} after {elapsed:.1f}s")
        raise HTTPException(
            status_code=408,  # Request Timeout
            detail=f"Timeout aguardando conclusão do job após {timeout}s. Use GET /jobs/{job_id} para verificar status atual."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error waiting for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao aguardar job: {str(e)}")

@app.get("/jobs/{job_id}/stream", tags=["Jobs"])
async def stream_job_progress(
    job_id: str,
    timeout: int = 600
):
    """
    📡 **Stream de progresso em tempo real (Server-Sent Events)**
    
    Este endpoint retorna um **stream de eventos** com atualizações do progresso:
    - Conexão permanece aberta
    - Envia eventos SSE a cada atualização
    - Cliente recebe progresso em tempo real
    - Fecha automaticamente quando job finaliza ou timeout
    
    **Formato de eventos:**
    ```
    event: progress
    data: {"status": "processing", "progress": 45.5, "stage": "transcribing"}
    
    event: completed
    data: {"status": "completed", "progress": 100.0, "message": "Job finalizado!"}
    
    event: error
    data: {"status": "failed", "error": "Erro na transcrição"}
    ```
    
    **Uso com JavaScript:**
    ```javascript
    const eventSource = new EventSource('/jobs/{job_id}/stream');
    
    eventSource.addEventListener('progress', (e) => {
        const data = JSON.parse(e.data);
        console.log(`Progresso: ${data.progress}%`);
    });
    
    eventSource.addEventListener('completed', (e) => {
        const data = JSON.parse(e.data);
        console.log('Job concluído!', data);
        eventSource.close();
    });
    ```
    
    **Parâmetros:**
    - `timeout`: Tempo máximo em segundos (padrão: 600)
    """
    async def event_generator():
        """Gera eventos SSE com progresso do job"""
        start_time = datetime.now()
        max_wait = timedelta(seconds=timeout)
        poll_interval = 1  # Atualiza a cada 1 segundo
        last_progress = -1
        
        logger.info(f"Starting SSE stream for job {job_id}")
        
        try:
            # Envia evento inicial
            yield f"event: connected\ndata: {json.dumps({'message': 'Conectado ao stream', 'job_id': job_id})}\n\n"
            
            while datetime.now() - start_time < max_wait:
                job = redis_store.get_job(job_id)
                
                if not job:
                    yield f"event: error\ndata: {json.dumps({'error': 'Job não encontrado', 'job_id': job_id})}\n\n"
                    break
                
                # Envia evento de progresso (apenas se mudou)
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
                            "transcription": job.transcription_stage.progress
                        }
                    }
                    
                    yield f"event: progress\ndata: {json.dumps(progress_data)}\n\n"
                    last_progress = job.overall_progress
                
                # Verifica se finalizou
                if job.status == PipelineStatus.COMPLETED:
                    completed_data = {
                        "job_id": job.id,
                        "status": "completed",
                        "progress": 100.0,
                        "message": "Pipeline concluído com sucesso!",
                        "transcription_file": job.transcription_file,
                        "audio_file": job.audio_file,
                        "completed_at": job.completed_at.isoformat() if job.completed_at else None
                    }
                    yield f"event: completed\ndata: {json.dumps(completed_data)}\n\n"
                    logger.info(f"Job {job_id} completed - closing SSE stream")
                    break
                
                elif job.status in [PipelineStatus.FAILED, PipelineStatus.CANCELLED]:
                    error_data = {
                        "job_id": job.id,
                        "status": job.status.value,
                        "error": job.error_message or "Job falhou",
                        "completed_at": job.completed_at.isoformat() if job.completed_at else None
                    }
                    yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
                    logger.warning(f"Job {job_id} failed - closing SSE stream")
                    break
                
                # Aguarda próximo poll
                await asyncio.sleep(poll_interval)
            
            # Timeout
            if datetime.now() - start_time >= max_wait:
                timeout_data = {
                    "job_id": job_id,
                    "error": f"Timeout após {timeout}s",
                    "message": f"Use GET /jobs/{job_id} para verificar status"
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
            "X-Accel-Buffering": "no"  # Nginx: desabilita buffering
        }
    )

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
