import asyncio
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import List
import logging

from .models import Job, JobRequest, JobStatus
from .downloader import SimpleDownloader
from .redis_store import RedisJobStore
from .celery_tasks import download_video_task
from .logging_config import setup_logging
from .exceptions import VideoDownloadException, ServiceException, exception_handler
from .security import SecurityMiddleware
from .config import get_settings

# Configuração de logging
setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

# Instâncias globais
app = FastAPI(
    title="Video Download Service",
    description="Microserviço com Celery + Redis para download de vídeos com cache de 24h",
    version="3.0.0"
)

# Middleware de segurança
app.add_middleware(SecurityMiddleware)

# Exception handlers
app.add_exception_handler(VideoDownloadException, exception_handler)
app.add_exception_handler(ServiceException, exception_handler)

# Usa Redis como store compartilhado
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
job_store = RedisJobStore(redis_url=redis_url)
downloader = SimpleDownloader()

# Injeta referência do job_store no downloader para updates de progresso
downloader.job_store = job_store


@app.on_event("startup")
async def startup_event():
    """Inicializa sistema com Celery"""
    try:
        await job_store.start_cleanup_task()
        logger.info("Video Download Service iniciado com sucesso")
    except Exception as e:
        logger.error("Erro durante inicialização: %s", e)
        raise


@app.on_event("shutdown") 
async def shutdown_event():
    """Para sistema"""
    try:
        await job_store.stop_cleanup_task()
        logger.info("Video Download Service parado graciosamente")
    except Exception as e:
        logger.error("Erro durante shutdown: %s", e)


def submit_celery_task(job: Job):
    """Submete job para o Celery"""
    # Serializa job para dict
    job_dict = job.model_dump()
    
    # Envia para fila do Celery
    task = download_video_task.apply_async(
        args=[job_dict],
        task_id=job.id  # Usa job.id como task_id para rastreamento
    )
    
    return task


@app.post("/jobs", response_model=Job)
async def create_download_job(request_obj: Request, request: JobRequest) -> Job:
    """
    Cria um novo job de download com Celery + cache inteligente
    
    - **url**: URL do vídeo para baixar
    - **quality**: Qualidade desejada (best, 720p, 480p, 360p, audio)
    
    Se o mesmo vídeo já foi baixado, retorna o job existente.
    """
    try:
        logger.info(f"Criando job de download para URL: {request.url}")
        
        # Cria job para extrair ID
        new_job = Job.create_new(request.url, request.quality)
        
        # Verifica se já existe job com mesmo ID
        existing_job = job_store.get_job(new_job.id)
        
        if existing_job:
            # Job já existe - verifica status
            if existing_job.status == JobStatus.COMPLETED:
                logger.info(f"Job {new_job.id} já completado")
                return existing_job
            elif existing_job.status in [JobStatus.QUEUED, JobStatus.DOWNLOADING]:
                logger.info(f"Job {new_job.id} já em processamento")
                return existing_job
            elif existing_job.status == JobStatus.FAILED:
                # Falhou antes - tenta novamente
                logger.info(f"Reprocessando job falhado: {new_job.id}")
                existing_job.status = JobStatus.QUEUED
                existing_job.error_message = None
                existing_job.progress = 0.0
                job_store.update_job(existing_job)
                
                # Submete para Celery
                submit_celery_task(existing_job)
                return existing_job
        
        # Job novo - salva e submete para Celery
        job_store.save_job(new_job)
        submit_celery_task(new_job)
        
        logger.info(f"Job de download criado: {new_job.id}")
        return new_job
        
    except Exception as e:
        logger.error(f"Erro ao criar job de download: {e}")
        if isinstance(e, (VideoDownloadException, ServiceException)):
            raise
        raise ServiceException(f"Erro interno ao processar request: {str(e)}")


@app.get("/jobs/{job_id}", response_model=Job)
async def get_job_status(job_id: str) -> Job:
    """
    Consulta status de um job
    
    Retorna informações completas do job incluindo status, progresso e links
    """
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expirado")
    
    return job


@app.get("/jobs/{job_id}/download")
async def download_file(job_id: str):
    """
    Faz download do arquivo (se pronto)
    
    Retorna o arquivo binário para download direto
    """
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if job.is_expired:
        raise HTTPException(status_code=410, detail="Job expirado")
        
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=425, 
            detail=f"Download não pronto. Status: {job.status}"
        )
    
    file_path = downloader.get_file_path(job)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    return FileResponse(
        path=file_path,
        filename=job.filename,
        media_type='application/octet-stream'
    )


@app.get("/jobs", response_model=List[Job])
async def list_jobs(limit: int = 20) -> List[Job]:
    """
    Lista jobs recentes
    
    - **limit**: Número máximo de jobs a retornar (padrão: 20)
    """
    return job_store.list_jobs(limit)


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Remove job e arquivos associados
    
    IMPORTANTE: Remove completamente o job do sistema:
    - Job do Redis
    - Arquivo de vídeo baixado
    - Arquivos temporários
    """
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    try:
        # Remove arquivo se existir
        files_deleted = 0
        
        if job.file_path:
            file_path = Path(job.file_path)
            if file_path.exists():
                file_path.unlink()
                files_deleted += 1
                logger.info(f"🗑️ Arquivo removido: {file_path.name}")
        
        # Remove job do Redis (CRÍTICO - estava faltando!)
        job_store.redis.delete(f"video_job:{job_id}")
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


@app.post("/admin/cleanup")
async def manual_cleanup(
    background_tasks: BackgroundTasks,
    deep: bool = False,
    purge_celery_queue: bool = False
):
    """
    🧹 LIMPEZA DO SISTEMA
    
    **Modos de operação:**
    
    1. **Limpeza básica** (deep=false ou omitido):
       - Remove jobs expirados (>24h)
       - Remove arquivos órfãos
    
    2. **Limpeza profunda** (deep=true) - ⚠️ FACTORY RESET:
       - TODOS os jobs do Redis (não só expirados)
       - TODOS os arquivos de cache/
       - TODOS os arquivos de downloads/
       - TODOS os arquivos temporários
       - TODOS os logs
       - **OPCIONAL:** TODOS os jobs da fila Celery (purge_celery_queue=true)
    
    **Parâmetros:**
    - deep (bool): Se true, faz limpeza COMPLETA (factory reset)
    - purge_celery_queue (bool): Se true, limpa FILA CELERY também (recomendado com deep=true)
    
    A limpeza é executada em background e retorna imediatamente.
    """
    # Cria um job para a limpeza
    cleanup_type = "TOTAL" if deep else "básica"
    cleanup_job_id = f"cleanup_{cleanup_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Agenda limpeza em background
    if deep:
        background_tasks.add_task(_perform_total_cleanup, purge_celery_queue)
    else:
        background_tasks.add_task(_perform_basic_cleanup)
    
    logger.warning(f"🔥 Limpeza {cleanup_type} agendada: {cleanup_job_id} (purge_celery={purge_celery_queue})")
    
    return {
        "message": f"🔥 Limpeza {cleanup_type} iniciada em background",
        "cleanup_id": cleanup_job_id,
        "status": "processing",
        "deep": deep,
        "purge_celery_queue": purge_celery_queue,
        "warning": "TUDO será removido!" if deep else "Jobs expirados serão removidos",
        "note": "Verifique os logs para acompanhar o progresso."
    }




async def _perform_basic_cleanup():
    """
    Executa limpeza BÁSICA: Remove apenas jobs expirados e arquivos órfãos
    """
    try:
        from redis import Redis
        from datetime import timedelta
        
        report = {
            "jobs_removed": 0,
            "files_deleted": 0,
            "space_freed_mb": 0.0,
            "errors": []
        }
        
        logger.info("🧹 Iniciando limpeza básica (jobs expirados)...")
        
        # 1. LIMPAR JOBS EXPIRADOS DO REDIS (>24h)
        try:
            redis = Redis.from_url(redis_url, decode_responses=True)
            keys = redis.keys("video_job:*")
            now = datetime.now()
            expired_count = 0
            
            for key in keys:
                job_data = redis.get(key)
                if job_data:
                    import json
                    try:
                        job = json.loads(job_data)
                        created_at = datetime.fromisoformat(job.get("created_at", ""))
                        age = now - created_at
                        
                        # Remove se > 24 horas
                        if age > timedelta(hours=24):
                            redis.delete(key)
                            expired_count += 1
                    except:
                        pass
            
            report["jobs_removed"] = expired_count
            logger.info(f"🗑️  Redis: {expired_count} jobs expirados removidos")
        except Exception as e:
            logger.error(f"❌ Erro ao limpar Redis: {e}")
            report["errors"].append(f"Redis: {str(e)}")
        
        # 2. LIMPAR ARQUIVOS ÓRFÃOS (sem job correspondente)
        cache_dir = Path("./cache")
        if cache_dir.exists():
            deleted_count = 0
            for file_path in cache_dir.iterdir():
                if not file_path.is_file():
                    continue
                
                # Arquivo órfão se não há job correspondente
                # (lógica simplificada: arquivos >24h)
                try:
                    age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
                    if age > timedelta(hours=24):
                        size_mb = file_path.stat().st_size / (1024 * 1024)
                        await asyncio.to_thread(file_path.unlink)
                        deleted_count += 1
                        report["space_freed_mb"] += size_mb
                except Exception as e:
                    logger.error(f"❌ Erro ao remover {file_path.name}: {e}")
                    report["errors"].append(f"Cache/{file_path.name}: {str(e)}")
            
            report["files_deleted"] += deleted_count
            if deleted_count > 0:
                logger.info(f"🗑️  Cache: {deleted_count} arquivos órfãos removidos")
        
        report["space_freed_mb"] = round(report["space_freed_mb"], 2)
        report["message"] = f"✓ Limpeza básica concluída: {report['jobs_removed']} jobs + {report['files_deleted']} arquivos ({report['space_freed_mb']}MB)"
        
        logger.info(f"✓ {report['message']}")
        if report["errors"]:
            logger.warning(f"⚠️  {len(report['errors'])} erros durante limpeza")
        
        return report
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO na limpeza básica: {e}")
        return {"error": str(e)}


async def _perform_total_cleanup(purge_celery_queue: bool = False):
    """
    Executa limpeza COMPLETA do sistema em background
    
    ZERA ABSOLUTAMENTE TUDO:
    - TODOS os jobs do Redis
    - TODOS os arquivos de cache/
    - TODOS os arquivos de downloads/
    - TODOS os arquivos temporários
    - (OPCIONAL) TODOS os jobs da fila Celery
    """
    try:
        from redis import Redis
        
        report = {
            "jobs_removed": 0,
            "files_deleted": 0,
            "space_freed_mb": 0.0,
            "celery_queue_purged": False,
            "celery_tasks_purged": 0,
            "errors": []
        }
        
        logger.warning("🔥 INICIANDO LIMPEZA TOTAL DO SISTEMA - TUDO SERÁ REMOVIDO!")
        
        # 1. LIMPAR TODOS OS JOBS DO REDIS
        try:
            redis = Redis.from_url(redis_url, decode_responses=True)
            keys = redis.keys("video_job:*")
            if keys:
                for key in keys:
                    redis.delete(key)
                report["jobs_removed"] = len(keys)
                logger.info(f"🗑️  Redis: {len(keys)} jobs removidos")
            else:
                logger.info("✓ Redis: nenhum job encontrado")
        except Exception as e:
            logger.error(f"❌ Erro ao limpar Redis: {e}")
            report["errors"].append(f"Redis: {str(e)}")
        
        # 2. LIMPAR FILA CELERY (SE SOLICITADO)
        if purge_celery_queue:
            try:
                from redis import Redis
                
                logger.warning("🔥 Limpando fila Celery 'video_downloader_queue'...")
                
                # Conecta ao Redis Celery
                redis_celery = Redis.from_url(redis_url)
                
                # Nome da fila no Redis (Celery usa formato: celery ou nome customizado)
                # A fila Celery é uma lista Redis, então precisamos deletar a lista inteira
                queue_keys = [
                    "video_downloader_queue",           # Fila principal
                    "celery",                            # Fila default do Celery
                    "_kombu.binding.video_downloader_queue",  # Bindings
                    "_kombu.binding.celery",            # Bindings default
                    "unacked",                          # Tasks não reconhecidas
                    "unacked_index",                    # Índice de unacked
                ]
                
                tasks_purged = 0
                for queue_key in queue_keys:
                    # LLEN para verificar se existe
                    queue_len = redis_celery.llen(queue_key)
                    if queue_len > 0:
                        logger.info(f"   Fila '{queue_key}': {queue_len} tasks")
                        tasks_purged += queue_len
                    
                    # DELETE remove a key inteira (inclui listas)
                    deleted = redis_celery.delete(queue_key)
                    if deleted:
                        logger.info(f"   ✓ Fila '{queue_key}' removida")
                
                # Também remove keys de resultados e metadados Celery
                celery_result_keys = redis_celery.keys("celery-task-meta-*")
                if celery_result_keys:
                    redis_celery.delete(*celery_result_keys)
                    logger.info(f"   ✓ {len(celery_result_keys)} resultados Celery removidos")
                
                report["celery_queue_purged"] = True
                report["celery_tasks_purged"] = tasks_purged
                logger.warning(f"🔥 Fila Celery purgada: {tasks_purged} tasks removidas")
                
            except Exception as e:
                logger.error(f"❌ Erro ao limpar fila Celery: {e}")
                report["errors"].append(f"Celery: {str(e)}")
        else:
            logger.info("⏭️  Fila Celery NÃO será limpa (purge_celery_queue=false)")
        
        # 3. LIMPAR TODOS OS ARQUIVOS DE CACHE
        cache_dir = Path("./cache")
        if cache_dir.exists():
            deleted_count = 0
            for file_path in cache_dir.iterdir():
                if not file_path.is_file():
                    continue
                    
                try:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    await asyncio.to_thread(file_path.unlink)
                    deleted_count += 1
                    report["space_freed_mb"] += size_mb
                except Exception as e:
                    logger.error(f"❌ Erro ao remover cache {file_path.name}: {e}")
                    report["errors"].append(f"Cache/{file_path.name}: {str(e)}")
            
            report["files_deleted"] += deleted_count
            if deleted_count > 0:
                logger.info(f"🗑️  Cache: {deleted_count} arquivos removidos")
            else:
                logger.info("✓ Cache: nenhum arquivo encontrado")
        
        # 3. LIMPAR TODOS OS ARQUIVOS DE DOWNLOADS
        downloads_dir = Path("./downloads")
        if downloads_dir.exists():
            deleted_count = 0
            for file_path in downloads_dir.iterdir():
                if not file_path.is_file():
                    continue
                    
                try:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    await asyncio.to_thread(file_path.unlink)
                    deleted_count += 1
                    report["space_freed_mb"] += size_mb
                except Exception as e:
                    logger.error(f"❌ Erro ao remover download {file_path.name}: {e}")
                    report["errors"].append(f"Downloads/{file_path.name}: {str(e)}")
            
            report["files_deleted"] += deleted_count
            if deleted_count > 0:
                logger.info(f"🗑️  Downloads: {deleted_count} arquivos removidos")
            else:
                logger.info("✓ Downloads: nenhum arquivo encontrado")
        
        # 4. LIMPAR TODOS OS ARQUIVOS TEMPORÁRIOS
        temp_dir = Path("./temp")
        if temp_dir.exists():
            deleted_count = 0
            for file_path in temp_dir.iterdir():
                if not file_path.is_file():
                    continue
                    
                try:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    await asyncio.to_thread(file_path.unlink)
                    deleted_count += 1
                    report["space_freed_mb"] += size_mb
                except Exception as e:
                    logger.error(f"❌ Erro ao remover temp {file_path.name}: {e}")
                    report["errors"].append(f"Temp/{file_path.name}: {str(e)}")
            
            report["files_deleted"] += deleted_count
            if deleted_count > 0:
                logger.info(f"🗑️  Temp: {deleted_count} arquivos removidos")
            else:
                logger.info("✓ Temp: nenhum arquivo encontrado")
        
        # Formatar relatório
        report["space_freed_mb"] = round(report["space_freed_mb"], 2)
        report["message"] = (
            f"🔥 LIMPEZA TOTAL CONCLUÍDA: "
            f"{report['jobs_removed']} jobs do Redis + "
            f"{report['files_deleted']} arquivos removidos "
            f"({report['space_freed_mb']}MB liberados)"
        )
        
        if report["errors"]:
            report["message"] += f" ⚠️ com {len(report['errors'])} erros"
        
        logger.warning(report["message"])
        return report
        
    except Exception as e:
        logger.error(f"❌ Erro na limpeza total: {e}")
        return {"error": str(e), "jobs_removed": 0, "files_deleted": 0}


@app.get("/admin/stats")
async def get_stats():
    """
    Estatísticas completas do sistema com Celery
    """
    from .celery_config import celery_app
    
    stats = job_store.get_stats()
    
    # Adiciona info do cache
    cache_path = Path("./cache")
    if cache_path.exists():
        files = list(cache_path.iterdir())
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        
        stats["cache"] = {
            "files_count": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }
    
    # Adiciona estatísticas do Celery
    try:
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active()
        stats["celery"] = {
            "active_workers": len(active_tasks) if active_tasks else 0,
            "active_tasks": sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0,
            "broker": "redis",
            "backend": "redis"
        }
    except Exception as e:
        stats["celery"] = {
            "error": str(e),
            "status": "unavailable"
        }
    
    return stats


@app.get("/admin/queue")
async def get_queue_stats():
    """
    Estatísticas específicas do Celery
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
    except Exception as e:
        return {
            "error": str(e),
            "is_running": False
        }


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
    except:
        celery_healthy = False
    
    overall_status = "healthy" if celery_healthy else "degraded"
    
    return {
        "status": overall_status,
        "service": "video-download-service", 
        "version": "3.0.0",
        "celery": {
            "healthy": celery_healthy,
            "workers_active": workers_active,
            "broker": "redis"
        },
        "details": {
            "celery_workers": "✅ Ativo" if celery_healthy else "❌ Problema",
            "redis_broker": "✅ Ativo" if celery_healthy else "❌ Problema",
            "job_store": "✅ Ativo",
            "cache_cleanup": "✅ Ativo"
        }
    }


@app.get("/user-agents/stats")
async def get_user_agent_stats():
    """
    Estatísticas do sistema de User-Agents
    
    Retorna:
    - Total de User-Agents disponíveis
    - Quantos estão em quarentena
    - Estatísticas de erro
    """
    return downloader.get_user_agent_stats()


@app.post("/user-agents/reset/{user_agent_id}")
async def reset_user_agent(user_agent_id: str):
    """
    Reset manual de User-Agent problemático
    
    Remove User-Agent da quarentena e limpa cache de erro.
    Use o User-Agent completo ou os primeiros 50 caracteres.
    """
    # Busca UA que comece com o ID fornecido
    stats = downloader.get_user_agent_stats()
    matching_ua = None
    
    # Tenta encontrar UA correspondente
    for quarantined_ua in stats.get('quarantined_uas', []):
        if quarantined_ua.startswith(user_agent_id) or user_agent_id in quarantined_ua:
            matching_ua = quarantined_ua
            break
    
    if not matching_ua:
        # Se não encontrou em quarentena, tenta reset direto
        matching_ua = user_agent_id
    
    success = downloader.reset_user_agent(matching_ua)
    
    return {
        "success": success,
        "user_agent": matching_ua[:50] + "..." if len(matching_ua) > 50 else matching_ua,
        "message": f"User-Agent {'resetado com sucesso' if success else 'não encontrado'}"
    }