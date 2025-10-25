#!/usr/bin/env python3
"""
Tasks do Celery para normalização de áudio
"""

import os
from celery import Task
from .celery_config import celery_app
from .models import Job, JobStatus
from .processor import TranscriptionProcessor
from .redis_store import RedisJobStore
import logging

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """Task base com callbacks para atualização de progresso"""
    def __init__(self):
        super().__init__()
        self._processor = None
        self._job_store = None

    def run(self, *args, **kwargs):
        """Implementação abstrata exigida pelo Celery"""
        return None

    @property
    def processor(self):
        if self._processor is None:
            self._processor = TranscriptionProcessor()
            if self._job_store:
                self._processor.job_store = self._job_store
        return self._processor

    @property
    def job_store(self):
        if self._job_store is None:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self._job_store = RedisJobStore(redis_url=redis_url)
            if self._processor:
                self._processor.job_store = self._job_store
        return self._job_store



@celery_app.task(bind=True, base=CallbackTask, name='transcribe_audio_task')
def transcribe_audio_task(self, job_dict: dict) -> dict:
    """
    Task do Celery para transcrição de áudio
    Args:
        job_dict: Job serializado como dicionário
    Returns:
        Job atualizado como dicionário
    """
    job = Job(**job_dict)
    logger.info("Iniciando transcrição do job %s", job.id)
    try:
        job.status = JobStatus.PROCESSING
        job.progress = 0.0
        self.job_store.update_job(job)
        result_job = self.processor.transcribe_audio(job)
        self.job_store.update_job(result_job)
        logger.info("Job %s concluído: %s", job.id, result_job.status)
        return result_job.model_dump()
    except (RuntimeError, ValueError, OSError) as e:
        logger.error("Erro ao processar tarefa Celery: %s", e)
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        self.job_store.update_job(job)
        return job.model_dump()
    except Exception as e:
        logger.error("Erro inesperado ao processar tarefa Celery: %s", e)
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        self.job_store.update_job(job)
        return job.model_dump()


@celery_app.task(name='cleanup_expired_jobs')
def cleanup_expired_jobs_task():
    """Task periódica para limpeza de jobs expirados"""
    import os
    import asyncio
    from .redis_store import RedisJobStore
    
    logger.info("Executando limpeza de jobs expirados")
    
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    store = RedisJobStore(redis_url=redis_url)
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    expired = loop.run_until_complete(store.cleanup_expired())
    
    return {"status": "completed", "expired_jobs": expired}
