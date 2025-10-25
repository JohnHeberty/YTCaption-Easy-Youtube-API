#!/usr/bin/env python3
"""
Tasks do Celery para normalização de áudio
"""

import os
import logging
import asyncio
from pydantic import ValidationError
from celery import Task
from .celery_config import celery_app
from .models import Job, JobStatus
from .processor import AudioProcessor
from .redis_store import RedisJobStore
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

logger = logging.getLogger(__name__)

class CallbackTask(Task):
    def run(self, *args, **kwargs) -> None:
        """
        Método abstrato para tasks com callback.
        """
        raise NotImplementedError("CallbackTask não implementa run diretamente.")
    # Task base com callbacks para atualização de progresso
    
    def __init__(self):
        super().__init__()
        self._processor = None
        self._job_store = None
    
    @property
    def processor(self):
        if self._processor is None:
            self._processor = AudioProcessor()
            if self._job_store:
                self._processor.job_store = self._job_store
        return self._processor
    
    @property
    def job_store(self):
        if self._job_store is None:
            redis_url = os.getenv('REDIS_URL', None)
            self._job_store = RedisJobStore(redis_url=redis_url)
            if self._processor:
                self._processor.job_store = self._job_store
        return self._job_store


@celery_app.task(bind=True, base=CallbackTask, name='normalize_audio_task', autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})  # pylint: disable=line-too-long
@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
def normalize_audio_task(self, job_dict: dict) -> dict:
    """
    Task do Celery para normalização de áudio.
    Args:
        job_dict (dict): Job serializado como dicionário.
    Returns:
        dict: Job atualizado como dicionário.
    """
    # Garante que todos os campos do modelo estejam presentes
    # ValidationError já importado no topo
    try:
        job = Job(**job_dict)
    except ValidationError as ve:
        logger.error("Erro de validação ao reconstruir job: %s", ve)
        # Preenche campos ausentes com valores do modelo
        fields = {field: job_dict.get(field, Job.model_fields[field].default) for field in Job.model_fields}
        job = Job(**fields)
    logger.info("Iniciando processamento do job %s", job.id)
    try:
        # Atualiza status para processing no Redis (com retry)
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
        def update_job_status(job):
            self.job_store.update_job(job)
        job.status = JobStatus.PROCESSING
        job.progress = 0.0
        update_job_status(job)
        # Executa processamento
        result_job = self.processor.process_audio(job)
        if not isinstance(result_job, Job):
            logger.error("process_audio retornou valor inválido para job %s, marcando como falha.", job.id)
            job.status = JobStatus.FAILED
            job.error_message = "process_audio retornou valor inválido"
            self.job_store.update_job(job)
            return job.model_dump()
        # Atualiza resultado final no Redis
        self.job_store.update_job(result_job)
        logger.info("Job %s concluído: %s", result_job.id, result_job.status)
        return result_job.model_dump()
    except (OSError, RuntimeError) as exc:
        logger.error("Erro no job %s: %s", job.id, exc)
        job.status = JobStatus.FAILED
        job.error_message = str(exc)
        self.job_store.update_job(job)
        return job.model_dump()


@celery_app.task(name='cleanup_expired_jobs')
def cleanup_expired_jobs_task():
    """
    Task periódica para limpeza de jobs expirados.
    Returns:
        dict: Status e quantidade de jobs expirados.
    """
    # Docstring já definida acima
    # imports já realizados no topo do arquivo
    
    logger.info("Executando limpeza de jobs expirados")
    
    redis_url = os.getenv('REDIS_URL', None)
    store = RedisJobStore(redis_url=redis_url)
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    expired = loop.run_until_complete(store.cleanup_expired())
    return {"status": "completed", "expired_jobs": expired}
