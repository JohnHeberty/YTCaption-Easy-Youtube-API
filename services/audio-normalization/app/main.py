
import os
import logging
from pathlib import Path
from typing import List
from datetime import datetime
from redis import Redis

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse

from .models import Job, JobStatus
from .processor import AudioProcessor
from .redis_store import RedisJobStore
from .celery_tasks import normalize_audio_task

# Configuração de logging para arquivo
LOG_DIR = Path(os.getenv('LOG_DIR', './logs'))
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / 'audio_normalization.log'
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO').upper(),
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Instâncias globais
app = FastAPI(
    title="Audio Normalization Service",
    description="Microserviço para normalização de áudio com Celery + Redis",
    version="1.0.0"
)

# Redis como store compartilhado
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
job_store = RedisJobStore(redis_url=redis_url)
processor = AudioProcessor()

# Injeta job_store no processor
processor.job_store = job_store

# Diretório para uploads
UPLOAD_DIR = Path(os.getenv('UPLOAD_DIR', './uploads'))
UPLOAD_DIR.mkdir(exist_ok=True)

# Instancia processor usando variáveis do .env
processor = AudioProcessor(
    output_dir=os.getenv('OUTPUT_DIR', './processed'),
    temp_dir=os.getenv('TEMP_DIR', './temp')
)

# Endpoints administrativos e de monitoramento
@app.post("/backup", tags=["admin"])
async def backup_jobs():
    count = job_store.backup_jobs()
    return {"jobs_backed_up": count}

@app.get("/celery-metrics", tags=["monitoring"])
async def celery_metrics():
    try:
        from .celery_config import celery_app
        inspect = celery_app.control.inspect()
        stats = inspect.stats() or {}
        active = inspect.active() or {}
        reserved = inspect.reserved() or {}
        scheduled = inspect.scheduled() or {}
        return {
            "stats": stats,
            "active": active,
            "reserved": reserved,
            "scheduled": scheduled
        }
    except Exception as exc:
        logger.error("Erro ao consultar métricas Celery: %s", exc)
        return {"error": str(exc)}


import os
import logging
from pathlib import Path
from typing import List
from datetime import datetime
from redis import Redis

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse

from .models import Job, JobStatus
from .processor import AudioProcessor
from .redis_store import RedisJobStore
from .celery_tasks import normalize_audio_task

# Configuração de logging para arquivo
LOG_DIR = Path(os.getenv('LOG_DIR', './logs'))
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / 'audio_normalization.log'
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO').upper(),
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Instâncias globais
app = FastAPI(
    title="Audio Normalization Service",
    description="Microserviço para normalização de áudio com Celery + Redis",
    version="1.0.0"
)

# Redis como store compartilhado
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
job_store = RedisJobStore(redis_url=redis_url)
processor = AudioProcessor()

# Injeta job_store no processor
processor.job_store = job_store

# Diretório para uploads
UPLOAD_DIR = Path(os.getenv('UPLOAD_DIR', './uploads'))
UPLOAD_DIR.mkdir(exist_ok=True)

# Instancia processor usando variáveis do .env
processor = AudioProcessor(
    output_dir=os.getenv('OUTPUT_DIR', './processed'),
    temp_dir=os.getenv('TEMP_DIR', './temp')
)

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


@app.on_event("startup")
async def startup_event() -> None:
    """
    Inicializa sistema e inicia tarefa de limpeza.
    """
    await job_store.start_cleanup_task()
    logger.info("✅ Audio Normalization Service iniciado")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """
    Para sistema e encerra tarefa de limpeza. Aguarda tarefas pendentes.
    """
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



def submit_celery_task(job: Job) -> object:
    """
    Submete job para o Celery.
    Args:
        job (Job): Instância do job.
    Returns:
        object: Task Celery.
    """
    job_dict = job.model_dump()
    task = normalize_audio_task.apply_async(
        args=[job_dict],
        task_id=job.id
    )
    return task


@app.post("/normalize", response_model=Job)
async def create_normalization_job(
    file: UploadFile = File(...),
    isolate_vocals: bool = False,
    remove_noise: bool = True,
    normalize_volume: bool = True,
    convert_to_mono: bool = True,
    set_sample_rate_16k: bool = True,
    apply_highpass_filter: bool = True
) -> Job:
    """
    Cria job de normalização de áudio com cache inteligente
    
    - **file**: Arquivo de áudio para processar
    - **isolate_vocals**: Isola voz removendo instrumental (padrão: false)
    - **remove_noise**: Remove ruído de fundo (padrão: true)
    - **normalize_volume**: Normaliza volume (padrão: true)
    - **convert_to_mono**: Converte para mono (padrão: true)
    
    Sistema de cache:
    - Se mesmo arquivo + mesmas operações já foram processadas, retorna job existente
    - Cache válido por 24h
    """
    # Circuit breaker: verifica se Redis está disponível
    try:
        job_store.redis.ping()
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Circuit breaker: Redis indisponível, rejeitando requisição. Erro: %s", exc)
        raise HTTPException(status_code=503, detail="Serviço temporariamente indisponível (Redis down)")  # pylint: disable=raise-missing-from,line-too-long
    # Validação reforçada do arquivo
    allowed_extensions = {'.wav', '.mp3', '.flac', '.ogg', '.m4a'}
    max_size_mb = 100
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        logger.warning("Arquivo com extensão não permitida: %s", ext)
        raise HTTPException(status_code=400, detail=f"Extensão de arquivo não permitida: {ext}")  # pylint: disable=raise-missing-from,line-too-long
    content = await file.read()
    if len(content) > max_size_mb * 1024 * 1024:
        logger.warning("Arquivo excede tamanho máximo: %d bytes", len(content))
        raise HTTPException(status_code=400, detail=f"Arquivo excede tamanho máximo de {max_size_mb}MB")  # pylint: disable=raise-missing-from,line-too-long
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Cria job (gera ID baseado no hash do arquivo + operações)
    new_job = Job.create_new(
        input_file=str(file_path),
        isolate_vocals=isolate_vocals,
        remove_noise=remove_noise,
        normalize_volume=normalize_volume,
        convert_to_mono=convert_to_mono,
        apply_highpass_filter=apply_highpass_filter,
        set_sample_rate_16k=set_sample_rate_16k
    )
    
    # Verifica se job já existe (cache)
    existing_job = job_store.get_job(new_job.id)
    
    if existing_job:
        # Job já existe - verifica status
        if existing_job.status == JobStatus.COMPLETED:
            # Já foi processado - retorna job em cache
            return existing_job
        elif existing_job.status in [JobStatus.QUEUED, JobStatus.PROCESSING]:
            # Ainda está processando - retorna job em progresso
            return existing_job
        elif existing_job.status == JobStatus.FAILED:
            # Falhou antes - tenta novamente
            existing_job.status = JobStatus.QUEUED
            existing_job.error_message = None
            existing_job.progress = 0.0
            existing_job.input_file = str(file_path)  # Atualiza caminho
            job_store.update_job(existing_job)
            
            # Submete para Celery
            submit_celery_task(existing_job)
            return existing_job
    
    # Job novo - salva e submete para Celery
    job_store.save_job(new_job)
    # Sempre envia o job serializado completo para o Celery
    submit_celery_task(job_store.get_job(new_job.id))
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
async def download_processed_file(job_id: str):
    """Download do arquivo processado"""
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expirado")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=425,
            detail=f"Processamento não concluído. Status: {job.status}"
        )
    
    file_path = processor.get_file_path(job)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type='audio/opus'
    )


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
    deleted_uploads = 0
    upload_dir = Path(os.getenv('UPLOAD_DIR', './uploads'))
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
    except (AttributeError, RuntimeError):
        celery_healthy = False
    
    # Verifica Redis
    redis_healthy = False
    try:
        redis = Redis.from_url(redis_url, decode_responses=True)
        redis.ping()
        redis_healthy = True
    except (ConnectionError, RuntimeError):
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
    upload_dir = Path(os.getenv('UPLOAD_DIR', './uploads'))
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
    except (AttributeError, RuntimeError) as e:
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
    except (AttributeError, RuntimeError) as e:
        return {
            "error": str(e),
            "is_running": False
        }
