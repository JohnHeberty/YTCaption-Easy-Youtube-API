
import os
import logging
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import List
from datetime import datetime

from .models import Job, JobStatus
from .processor import TranscriptionProcessor
from .redis_store import RedisJobStore
from .celery_tasks import transcribe_audio_task

# Configuração de logging para arquivo
LOG_DIR = Path(os.getenv('LOG_DIR', './logs'))
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / 'audio_transcriber.log'
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO').upper(),
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

import asyncio

class CustomFastAPI(FastAPI):
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        except asyncio.CancelledError:
            # Silencia erro de cancelamento no shutdown
            if scope["type"] == "lifespan":
                pass
            else:
                raise

# Instância da aplicação FastAPI
app = CustomFastAPI(
    title="Audio Transcriber Service",
    description="Microserviço para transcrição de áudio com Celery + Redis",
    version="1.0.0"
)

# Redis como store compartilhado
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
job_store = RedisJobStore(redis_url=redis_url)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR = Path(os.getenv("PROCESSED_DIR", "./processed"))
PROCESSED_DIR.mkdir(exist_ok=True)
processor = TranscriptionProcessor(
    output_dir=os.getenv("WHISPER_OUTPUT_DIR", "./transcriptions"),
    model_dir=os.getenv("WHISPER_MODEL_DIR", "./models")
)

# Injeta job_store no processor
processor.job_store = job_store

# Endpoints de healthcheck
@app.get("/health", tags=["monitoring"])
async def health():
    """Healthcheck básico"""
    return JSONResponse(content={"status": "ok"})

@app.get("/ready", tags=["monitoring"])
async def ready():
    """Readiness check: verifica conexão Redis"""
    try:
        job_store.redis.ping()
        return JSONResponse(content={"status": "ready"})
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"Readiness check falhou: {e}")  # pylint: disable=logging-fstring-interpolation
        return JSONResponse(content={"status": "not ready", "error": str(e)}, status_code=503)


def submit_celery_task(job: Job):
    """Submete job para o Celery"""
    # Serializa job para dict
    job_dict = job.model_dump()
    
    # Envia para fila do Celery
    task = transcribe_audio_task.apply_async(
        args=[job_dict],
        task_id=job.id
    )
    return task

@app.on_event("startup")
async def startup_event():
    """Inicializa sistema"""
    await job_store.start_cleanup_task()
    logger.info("✅ Audio Transcriber Service iniciado")


@app.on_event("shutdown")
async def shutdown_event():
    """Para sistema. Aguarda tarefas pendentes."""
    await job_store.stop_cleanup_task()
    # Aguarda tasks Celery pendentes
    try:
        from .celery_config import celery_app
        inspect = celery_app.control.inspect()
        active = inspect.active() or {}
        if active:
            logger.info("Aguardando %d tarefas Celery pendentes...", sum(len(v) for v in active.values()))
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Erro ao consultar tarefas pendentes Celery no shutdown: %s", exc)
    logger.info("🛑 Serviço parado")


def submit_celery_task(job: Job):
    """Submete job para o Celery"""
    job_dict = job.model_dump()
    task = transcribe_audio_task.apply_async(
        args=[job_dict],
        task_id=job.id
    )
    return task


@app.post("/transcribe", response_model=Job)
async def create_transcription_job(
    file: UploadFile = File(...),
    language: str = "auto",
    output_format: str = "srt"
) -> Job:
    """
    Cria job de transcrição de áudio
    - **file**: Arquivo de áudio para transcrever
    - **language**: Idioma do áudio (pt, en, es, auto)
    - **output_format**: Formato de saída (srt, vtt, txt)
    """
    # Circuit breaker: verifica se Redis está disponível
    try:
        job_store.redis.ping()
    except Exception as exc:
        logger.error("Circuit breaker: Redis indisponível, rejeitando requisição. Erro: %s", exc)
        raise HTTPException(status_code=503, detail="Serviço temporariamente indisponível (Redis down)")
    
    # Validação reforçada do arquivo
    allowed_extensions = {'.wav', '.mp3', '.flac', '.ogg', '.m4a'}
    max_size_mb = 100
    ext = Path(file.filename).suffix.lower()
    
    if ext not in allowed_extensions:
        logger.warning("Arquivo com extensão não permitida: %s", ext)
        raise HTTPException(status_code=400, detail=f"Extensão de arquivo não permitida: {ext}")
    
    content = await file.read()
    if len(content) > max_size_mb * 1024 * 1024:
        logger.warning("Arquivo excede tamanho máximo: %d bytes", len(content))
        raise HTTPException(status_code=400, detail=f"Arquivo excede tamanho máximo de {max_size_mb}MB")
    
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        f.write(content)
    new_job = Job.create_new(
        input_file=str(file_path),
        language=language,
        output_format=output_format
    )
    existing_job = job_store.get_job(new_job.id)
    if existing_job and existing_job.status == JobStatus.COMPLETED:
        return existing_job
    job_store.save_job(new_job)
    submit_celery_task(new_job)
    return new_job


@app.get("/jobs/{job_id}", response_model=Job)
async def get_job_status(job_id: str) -> Job:
    """Consulta status de um job"""
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expirado")
    
    return job



@app.get("/jobs/{job_id}/download")
async def download_transcription_file(job_id: str):
    """Download do arquivo de legenda gerado (.srt/.vtt/.txt)"""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expirado")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=425,
            detail=f"Transcrição não concluída. Status: {job.status}"
        )
    file_path = Path(job.output_file)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo de transcrição não encontrado")
    media_types = {
        "srt": "application/x-subrip",
        "vtt": "text/vtt",
        "txt": "text/plain"
    }
    fmt = getattr(job, "output_format", "srt")
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type=media_types.get(fmt, "text/plain")
    )

@app.get("/jobs/{job_id}/text")
async def get_transcription_text(job_id: str):
    """Retorna texto completo da transcrição (sem timestamps)"""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=425,
            detail=f"Transcrição não concluída. Status: {job.status}"
        )
    return {
        "job_id": job.id,
        "text": job.transcription_text,
        "language": getattr(job, "detected_language", None),
        "segments_count": getattr(job, "segments_count", None),
        "duration": getattr(job, "audio_duration", None),
        "output_format": getattr(job, "output_format", None)
    }


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Cancela/deleta um job"""
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    # Remove arquivo processado se existir
    if job.output_file:
        file_path = Path(job.output_file)
        if file_path.exists():
            file_path.unlink()
    
    # Remove arquivo de input se existir
    if job.input_file:
        input_path = Path(job.input_file)
        if input_path.exists():
            input_path.unlink()
    
    # Remove do Redis
    from redis import Redis
    redis = Redis.from_url(redis_url, decode_responses=True)
    redis.delete(f"audio_job:{job_id}")
    
    return {"message": "Job deletado"}


@app.post("/admin/cleanup")
async def manual_cleanup():
    """
    Força limpeza manual de jobs e arquivos expirados
    """
    removed = await job_store.cleanup_expired()
    return {
    "message": "Limpeza concluída",
        "jobs_removed": removed,
        "timestamp": datetime.now().isoformat()
    }


@app.delete("/admin/cache")
async def clear_all_cache():
    """
    Limpa TODO o cache (jobs + arquivos)
    ⚠️ CUIDADO: Remove todos os jobs e arquivos processados
    """
    from redis import Redis
    
    # Limpa todos os jobs do Redis
    redis = Redis.from_url(redis_url, decode_responses=True)
    keys = redis.keys("audio_job:*")
    deleted_keys = 0
    
    for key in keys:
        redis.delete(key)
        deleted_keys += 1
    
    # Remove todos os arquivos processados
    processed_dir = Path("./processed")
    deleted_files = 0
    if processed_dir.exists():
        for file in processed_dir.iterdir():
            if file.is_file():
                file.unlink()
                deleted_files += 1
    
    # Remove todos os arquivos de upload
    upload_dir = Path("./uploads")
    deleted_uploads = 0
    if upload_dir.exists():
        for file in upload_dir.iterdir():
            if file.is_file():
                file.unlink()
                deleted_uploads += 1
    
    return {
        "message": "Cache completamente limpo",
        "redis_keys_deleted": deleted_keys,
        "processed_files_deleted": deleted_files,
        "upload_files_deleted": deleted_uploads,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/jobs", response_model=List[Job])
async def list_jobs(limit: int = 20) -> List[Job]:
    """Lista jobs recentes"""
    return job_store.list_jobs(limit)


@app.get("/health")
async def health_check():
    """
    Health check avançado com Celery
    """
    from .celery_config import celery_app
    
    # Verifica Celery
    celery_healthy = False
    workers_active = 0
    
    try:
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        celery_healthy = active_workers is not None
        workers_active = len(active_workers) if active_workers else 0
    except (RuntimeError, ValueError, OSError):
        celery_healthy = False
    
    # Verifica Redis
    redis_healthy = False
    try:
        from redis import Redis
        redis = Redis.from_url(redis_url, decode_responses=True)
        redis.ping()
        redis_healthy = True
    except (RuntimeError, ValueError, OSError):
        redis_healthy = False
    
    overall_status = "healthy" if (celery_healthy and redis_healthy) else "degraded"
    
    return {
        "status": overall_status,
        "service": "audio-normalization-service",
        "version": "2.0.0",
        "celery": {
            "healthy": celery_healthy,
            "workers_active": workers_active,
            "broker": "redis"
        },
        "redis": {
            "healthy": redis_healthy,
            "connection": "✅ Ativo" if redis_healthy else "❌ Problema"
        },
        "details": {
            "celery_workers": "✅ Ativo" if celery_healthy else "❌ Problema",
            "redis_broker": "✅ Ativo" if celery_healthy else "❌ Problema",
            "redis_store": "✅ Ativo" if redis_healthy else "❌ Problema",
            "job_store": "✅ Ativo",
            "cache_cleanup": "✅ Ativo"
        }
    }


@app.get("/admin/stats")
async def get_stats():
    """Estatísticas do sistema"""
    stats = job_store.get_stats()
    
    # Adiciona info de arquivos processados
    processed_dir = Path("./processed")
    if processed_dir.exists():
        files = list(processed_dir.iterdir())
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        
        stats["processed_files"] = {
            "count": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }
    
    # Adiciona info de uploads
    upload_dir = Path("./uploads")
    if upload_dir.exists():
        files = list(upload_dir.iterdir())
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        
        stats["upload_files"] = {
            "count": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }
    
    # Estatísticas do Celery
    try:
        from .celery_config import celery_app
        inspect = celery_app.control.inspect()
        
        active_tasks = inspect.active() or {}
        stats["celery"] = {
            "active_workers": len(active_tasks),
            "active_tasks": sum(len(tasks) for tasks in active_tasks.values()),
            "broker": "redis",
            "backend": "redis"
        }
    except (RuntimeError, ValueError, OSError) as e:
        logger.error("Erro inesperado ao obter estatísticas do Celery: %s", e)
        stats["celery"] = {
            "error": str(e),
            "status": "unavailable"
        }
    
    return stats


@app.get("/admin/queue")
async def get_queue_stats():
    """
    Estatísticas específicas da fila Celery
    """
    from .celery_config import celery_app
    
    try:
        inspect = celery_app.control.inspect()
        
        # Workers ativos
        active_workers = inspect.active()
        registered = inspect.registered()
        
        return {
            "broker": "redis",
            "active_workers": len(active_workers) if active_workers else 0,
            "registered_tasks": list(registered.values())[0] if registered else [],
            "active_tasks": active_workers if active_workers else {},
            "is_running": active_workers is not None
        }
    except (RuntimeError, ValueError, OSError) as e:
        logger.error("Erro inesperado ao obter estatísticas da fila: %s", e)
        return {
            "error": str(e),
            "is_running": False
        }
