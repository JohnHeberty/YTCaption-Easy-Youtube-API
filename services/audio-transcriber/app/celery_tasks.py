import os
import logging
import asyncio
from celery import Task
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import Job, JobStatus
from .processor import TranscriptionProcessor
from .redis_store import RedisJobStore
from .celery_config import celery_app

logger = logging.getLogger(__name__)


class TranscriptionTask(Task):
    def __init__(self):
        self._processor = None
        self._job_store = None

    @property
    def processor(self):
        if self._processor is None:
            self._processor = TranscriptionProcessor(
                output_dir=os.getenv("WHISPER_OUTPUT_DIR", "./transcriptions"),
                model_dir=os.getenv("WHISPER_MODEL_DIR", "./models")
            )
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


@celery_app.task(bind=True, base=TranscriptionTask, name='transcribe_audio')
def transcribe_audio_task(self, job_dict):
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
        
    except Exception as e:
        logger.error("Erro ao processar tarefa Celery: %s", e)
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        self.job_store.update_job(job)
        return job.model_dump()


@celery_app.task(name='cleanup_expired_jobs')
def cleanup_expired_jobs_task():
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
