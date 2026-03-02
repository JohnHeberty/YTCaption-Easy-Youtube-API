#!/usr/bin/env python3
"""
Tasks do Celery para download de vídeos
"""

import os
import logging
from datetime import datetime
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

from celery import Task
from celery import signals
from .celery_config import celery_app
from ..core.models import Job, JobStatus
from ..domain.downloader import SimpleDownloader
from .redis_store import RedisJobStore
from ..core.config import get_settings

logger = logging.getLogger(__name__)


# ==========================================
# SIGNAL HANDLERS PARA SINCRONIZAÇÃO REDIS
# ==========================================

@signals.task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **kw):
    """
    Signal handler disparado quando uma task falha
    Garante que o Redis Store seja atualizado mesmo em falhas inesperadas
    """
    logger.error(f"🔴 SIGNAL: Task failure detected for task_id={task_id}, exception={exception}")
    
    try:
        # Extrai job_dict dos args
        if args and len(args) > 0 and isinstance(args[0], dict):
            job_dict = args[0]
            job_id = job_dict.get('id', 'unknown')
            
            # Atualiza Redis Store
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            store = RedisJobStore(redis_url=redis_url)
            
            try:
                # Reconstrói job e marca como FAILED
                job = Job(**job_dict)
                job.status = JobStatus.FAILED
                job.error_message = f"Task failed: {str(exception)}"
                job.progress = 0.0
                
                store.update_job(job)
                logger.info(f"✅ SIGNAL: Updated Redis Store for failed job {job_id}")
            except Exception as update_err:
                logger.error(f"❌ SIGNAL: Failed to update Redis Store: {update_err}")
    except Exception as handler_err:
        logger.error(f"❌ SIGNAL HANDLER ERROR: {handler_err}")


@signals.task_revoked.connect
def task_revoked_handler(sender=None, request=None, terminated=None, signum=None, expired=None, **kw):
    """
    Signal handler disparado quando uma task é revogada (killed, canceled)
    """
    task_id = request.id if request else 'unknown'
    logger.error(f"🔴 SIGNAL: Task revoked task_id={task_id}, terminated={terminated}, signum={signum}")
    
    try:
        # Tenta extrair job_dict do request
        if request and hasattr(request, 'args') and request.args and len(request.args) > 0:
            job_dict = request.args[0]
            if isinstance(job_dict, dict):
                job_id = job_dict.get('id', 'unknown')
                
                redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
                store = RedisJobStore(redis_url=redis_url)
                
                try:
                    job = Job(**job_dict)
                    job.status = JobStatus.FAILED
                    job.error_message = f"Task revoked: terminated={terminated}, signal={signum}"
                    job.progress = 0.0
                    
                    store.update_job(job)
                    logger.info(f"✅ SIGNAL: Updated Redis Store for revoked job {job_id}")
                except Exception as update_err:
                    logger.error(f"❌ SIGNAL: Failed to update Redis Store: {update_err}")
    except Exception as handler_err:
        logger.error(f"❌ SIGNAL HANDLER ERROR: {handler_err}")


class CallbackTask(Task):
    """Task base com callbacks para atualização de progresso"""
    
    def __init__(self):
        super().__init__()
        self._downloader = None
        self._job_store = None
    
    @property
    def downloader(self):
        if self._downloader is None:
            self._downloader = SimpleDownloader(cache_dir=get_settings().cache_dir)
            # Injeta job_store no downloader
            if self._job_store:
                self._downloader.job_store = self._job_store
        return self._downloader
    
    @property
    def job_store(self):
        """Cria job_store compartilhado via Redis"""
        if self._job_store is None:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self._job_store = RedisJobStore(redis_url=redis_url)
            # Injeta no downloader também
            if self._downloader:
                self._downloader.job_store = self._job_store
        return self._job_store
    
    def run(self, *args, **kwargs):
        """Método abstrato obrigatório (não usado, mas precisa existir)"""
        return None  # Retorna None em vez de pass


@celery_app.task(
    bind=True, 
    base=CallbackTask, 
    name='download_video_task',
    autoretry_for=(ConnectionError, IOError, OSError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=1800,  # 30 minutos
    time_limit=2400  # 40 minutos
)
def download_video_task(self, job_dict: dict) -> dict:
    """
    Task resiliente do Celery para download de vídeos do YouTube.
    
    Retry Policy:
    - Auto-retry em: ConnectionError, IOError, OSError
    - Max retries: 3
    - Backoff exponencial com jitter
    - Soft timeout: 30 minutos
    - Hard timeout: 40 minutos
    
    Args:
        job_dict: Job serializado como dicionário
        
    Returns:
        Job atualizado como dicionário
    """
    from celery.exceptions import Ignore, WorkerLostError, SoftTimeLimitExceeded
    
    job_id = job_dict.get('id', 'unknown')
    retry_count = self.request.retries
    logger.info(f"🚀 Iniciando download do job {job_id} (tentativa {retry_count + 1}/{self.max_retries + 1})")
    
    try:
        # Reconstitui job
        try:
            job = Job(**job_dict)
            logger.info(f"✅ Job {job_id} reconstituído com sucesso")
        except Exception as ve:
            logger.error(f"❌ Erro de validação ao reconstituir job {job_id}: {ve}")
            # Não usa update_state aqui - pode causar crash recursivo
            raise Ignore()
        
        # Atualiza status
        job.status = JobStatus.DOWNLOADING
        job.started_at = now_brazil()  # Marca quando começou
        job.progress = 0.0
        self.job_store.update_job(job)
        
        # Remove update_state - apenas atualiza Redis Store
        # self.update_state causa problemas quando há resultados corrompidos
        
        # Executa download
        try:
            result_job = self.downloader._sync_download(job)  # noqa: SLF001
            self.job_store.update_job(result_job)
            
            logger.info(f"✅ Job {job_id} concluído: {result_job.status}")
            
            # Se falhou, raise Ignore para que Celery não faça retry
            # O Redis Store já foi atualizado pelo downloader
            if result_job.status != JobStatus.COMPLETED:
                logger.warning(f"Job {job_id} falhou durante download: {result_job.error_message}")
                raise Ignore()
            
            return result_job.model_dump()
            
        except SoftTimeLimitExceeded:
            logger.error(f"⏰ Job {job_id} excedeu soft time limit")
            job.status = JobStatus.FAILED
            job.error_message = "Download excedeu o tempo limite (30 minutos)"
            self.job_store.update_job(job)
            # Redis já atualizado, apenas sinaliza Ignore
            raise Ignore()
            
    except WorkerLostError as worker_lost_err:
        error_msg = f"Worker perdido durante download: {str(worker_lost_err)}"
        logger.critical(f"💀 Job {job_id} WORKER LOST: {error_msg}")
        
        if 'job' in locals():
            job.status = JobStatus.FAILED
            job.error_message = error_msg
            try:
                self.job_store.update_job(job)
            except Exception:
                pass
        
        # Não faz update_state - worker está perdido mesmo
        raise Ignore()
        
    except Ignore:
        raise
        
    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"💥 Erro no download do job {job_id}: {error_msg}", exc_info=True)
        
        if 'job' in locals():
            job.status = JobStatus.FAILED
            job.error_message = error_msg
            try:
                self.job_store.update_job(job)
            except Exception as update_exc:
                logger.error(f"Falha ao atualizar job no Redis: {update_exc}")
        
        # Redis já atualizado (ou falhou), apenas sinaliza Ignore
        # Não usa update_state para evitar crash recursivo
        raise Ignore()



@celery_app.task(name='cleanup_expired_jobs')
def cleanup_expired_jobs_task():
    """
    Task periódica para limpeza de jobs expirados via Redis
    """
    import asyncio
    
    logger.info("Executando limpeza de jobs expirados")
    
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    store = RedisJobStore(redis_url=redis_url)
    
    # Executa cleanup síncrono
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    expired = loop.run_until_complete(store.cleanup_expired())
    
    return {"status": "completed", "expired_jobs": expired}
