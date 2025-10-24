#!/usr/bin/env python3
"""
Tasks do Celery para download de vídeos
"""

import os
from celery import Task
from .celery_config import celery_app
from .models import Job, JobStatus
from .downloader import SimpleDownloader
from .redis_store import RedisJobStore
import logging

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """Task base com callbacks para atualização de progresso"""
    
    def __init__(self):
        super().__init__()
        self._downloader = None
        self._job_store = None
    
    @property
    def downloader(self):
        if self._downloader is None:
            self._downloader = SimpleDownloader()
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


@celery_app.task(bind=True, base=CallbackTask, name='download_video_task')
def download_video_task(self, job_dict: dict) -> dict:
    """
    Task do Celery para download de vídeos
    
    Args:
        job_dict: Job serializado como dicionário
        
    Returns:
        Job atualizado como dicionário
    """
    # Reconstrói o Job a partir do dict
    job = Job(**job_dict)
    
    logger.info(f"Iniciando download do job {job.id}")
    
    try:
        # Atualiza status para downloading no Redis
        job.status = JobStatus.DOWNLOADING
        job.progress = 0.0
        self.job_store.update_job(job)
        
        # Executa download (job_store já está injetado no downloader)
        result_job = self.downloader._sync_download(job)
        
        # Atualiza resultado final no Redis
        self.job_store.update_job(result_job)
        
        logger.info(f"Job {job.id} concluído: {result_job.status}")
        
        # Retorna job serializado
        return result_job.model_dump()
        
    except Exception as e:
        logger.error(f"Erro no download do job {job.id}: {e}")
        
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        self.job_store.update_job(job)
        
        return job.model_dump()


@celery_app.task(name='cleanup_expired_jobs')
def cleanup_expired_jobs_task():
    """
    Task periódica para limpeza de jobs expirados via Redis
    """
    import os
    from .redis_store import RedisJobStore
    
    logger.info("Executando limpeza de jobs expirados")
    
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    store = RedisJobStore(redis_url=redis_url)
    
    # Executa cleanup síncrono
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    expired = loop.run_until_complete(store.cleanup_expired())
    
    return {"status": "completed", "expired_jobs": expired}
