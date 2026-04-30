#!/usr/bin/env python3
"""
Tasks do Celery para download de vídeos (v2 com job_utils)
"""

import os
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
from common.log_utils import get_logger
from .celery_config import celery_app
from common.job_utils.models import JobStatus
from ..core.models import VideoDownloadJob
from ..services.video_downloader import YDLPVideoDownloader as SimpleDownloader
from .redis_store import VideoDownloadJobStore
from ..core.config import get_settings

logger = get_logger(__name__)


# ==========================================
# SIGNAL HANDLERS PARA SINCRONIZACAO REDIS
# ==========================================

@signals.task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **kw):
    """
    Signal handler disparado quando uma task falha
    Garante que o Redis Store seja atualizado mesmo em falhas inesperadas
    """
    logger.error(f"🔴 SIGNAL: Task failure detected for task_id={task_id}, exception={exception}")
    
    try:
        if args and len(args) > 0 and isinstance(args[0], dict):
            job_dict = args[0]
            job_id = job_dict.get('id', 'unknown')
            
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            store = VideoDownloadJobStore(redis_url=redis_url)
            
            try:
                job = VideoDownloadJob(**job_dict)
                job.mark_as_failed(f"Task failed: {str(exception)}", error_type=type(exception).__name__)
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
        if request and hasattr(request, 'args') and request.args and len(request.args) > 0:
            job_dict = request.args[0]
            if isinstance(job_dict, dict):
                job_id = job_dict.get('id', 'unknown')
                
                redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
                store = VideoDownloadJobStore(redis_url=redis_url)
                
                try:
                    job = VideoDownloadJob(**job_dict)
                    job.mark_as_failed(f"Task revoked: terminated={terminated}, signal={signum}")
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
        self._processor = None
    
    @property
    def downloader(self):
        if self._downloader is None:
            self._downloader = SimpleDownloader(cache_dir=get_settings().cache_dir)
            if self._job_store:
                self._downloader.job_store = self._job_store
        return self._downloader
    
    @property
    def job_store(self):
        if self._job_store is None:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self._job_store = VideoDownloadJobStore(redis_url=redis_url)
            if self._downloader:
                self._downloader.job_store = self._job_store
        return self._job_store
    
    def run(self, *args, **kwargs):
        return None


@celery_app.task(
    bind=True, 
    base=CallbackTask, 
    name='download_video_task',
    autoretry_for=(ConnectionError, IOError, OSError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=1800,
    time_limit=2400
)
def download_video_task(self, job_dict: dict) -> dict:
    """
    Task resiliente do Celery para download de vídeos do YouTube.
    """
    from celery.exceptions import Ignore, WorkerLostError, SoftTimeLimitExceeded
    
    job_id = job_dict.get('id', 'unknown')
    retry_count = self.request.retries
    logger.info(f"🚀 Iniciando download do job {job_id} (tentativa {retry_count + 1}/{self.max_retries + 1})")
    
    try:
        try:
            job = VideoDownloadJob(**job_dict)
            logger.info(f"✅ Job {job_id} reconstituído com sucesso")
        except Exception as ve:
            logger.error(f"❌ Erro de validação ao reconstituir job {job_id}: {ve}")
            raise Ignore()
        
        job.mark_as_processing("Downloading video")
        self.job_store.update_job(job)
        
        try:
            result_job = self.downloader._sync_download(job)
            self.job_store.update_job(result_job)
            
            logger.info(f"✅ Job {job_id} concluído: {result_job.status}")
            
            if result_job.status != JobStatus.COMPLETED:
                logger.warning(f"Job {job_id} falhou durante download: {result_job.error_message}")
                raise Ignore()
            
            return result_job.model_dump(mode="json")
            
        except SoftTimeLimitExceeded:
            logger.error(f"⏰ Job {job_id} excedeu soft time limit")
            job.mark_as_failed("Download excedeu o tempo limite (30 minutos)", error_type="Timeout")
            self.job_store.update_job(job)
            raise Ignore()
            
    except WorkerLostError as worker_lost_err:
        error_msg = f"Worker perdido durante download: {str(worker_lost_err)}"
        logger.critical(f"💀 Job {job_id} WORKER LOST: {error_msg}")
        
        if 'job' in locals():
            job.mark_as_failed(error_msg, error_type="WorkerLostError")
            try:
                self.job_store.update_job(job)
            except Exception:
                pass
        
        raise Ignore()
        
    except Ignore:
        raise
        
    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"💥 Erro no download do job {job_id}: {error_msg}", exc_info=True)
        
        if 'job' in locals():
            job.mark_as_failed(error_msg, error_type=type(exc).__name__)
            try:
                self.job_store.update_job(job)
            except Exception as update_exc:
                logger.error(f"Falha ao atualizar job no Redis: {update_exc}")
        
        raise Ignore()


@celery_app.task(name='cleanup_expired_jobs')
def cleanup_expired_jobs_task():
    """
    Task periódica para limpeza de jobs expirados via Redis
    """
    import asyncio
    
    logger.info("Executando limpeza de jobs expirados")
    
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    store = VideoDownloadJobStore(redis_url=redis_url)
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    expired = loop.run_until_complete(store.cleanup_expired())
    
    return {"status": "completed", "expired_jobs": expired}