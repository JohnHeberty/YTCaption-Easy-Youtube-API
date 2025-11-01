import os
import logging
import asyncio
from celery import Task
from celery import signals
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import Job, JobStatus
from .processor import TranscriptionProcessor
from .redis_store import RedisJobStore
from .celery_config import celery_app

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


@celery_app.task(
    bind=True, 
    base=TranscriptionTask, 
    name='transcribe_audio',
    autoretry_for=(ConnectionError, IOError, OSError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=2700,  # 45 minutos
    time_limit=3600  # 60 minutos
)
def transcribe_audio_task(self, job_dict):
    """
    Task resiliente para transcrição de áudio com Whisper.
    
    Retry Policy:
    - Auto-retry em: ConnectionError, IOError, OSError
    - Max retries: 3
    - Backoff exponencial com jitter
    - Soft timeout: 45 minutos
    - Hard timeout: 60 minutos
    """
    from celery.exceptions import Ignore, WorkerLostError, SoftTimeLimitExceeded
    from pydantic import ValidationError
    
    job_id = job_dict.get('id', 'unknown')
    retry_count = self.request.retries
    logger.info(f"🚀 Iniciando transcrição do job {job_id} (tentativa {retry_count + 1}/{self.max_retries + 1})")
    
    try:
        # Reconstitui job
        try:
            job = Job(**job_dict)
            logger.info(f"✅ Job {job_id} reconstituído com sucesso")
        except ValidationError as ve:
            logger.error(f"❌ Erro de validação ao reconstituir job {job_id}: {ve}")
            self.update_state(state='FAILURE', meta={
                'status': 'failed',
                'job_id': job_id,
                'error': f'Job validation failed: {str(ve)}',
                'progress': 0.0
            })
            raise Ignore()
        
        # Atualiza status
        job.status = JobStatus.PROCESSING
        job.progress = 0.0
        self.job_store.update_job(job)
        
        self.update_state(state='STARTED', meta={
            'status': 'processing',
            'job_id': job_id,
            'progress': 0.0
        })
        
        # Processa transcrição
        try:
            result_job = self.processor.transcribe_audio(job)
            self.job_store.update_job(result_job)
            
            logger.info(f"✅ Job {job_id} concluído: {result_job.status}")
            
            if result_job.status == JobStatus.COMPLETED:
                self.update_state(state='SUCCESS', meta={
                    'status': 'completed',
                    'job_id': job_id,
                    'output_file': result_job.output_file,
                    'progress': 100.0
                })
            else:
                self.update_state(state='FAILURE', meta={
                    'status': 'failed',
                    'job_id': job_id,
                    'error': result_job.error_message or 'Unknown error',
                    'progress': result_job.progress
                })
                raise Ignore()
            
            return result_job.model_dump()
            
        except SoftTimeLimitExceeded:
            logger.error(f"⏰ Job {job_id} excedeu soft time limit")
            job.status = JobStatus.FAILED
            job.error_message = "Transcrição excedeu o tempo limite (45 minutos)"
            self.job_store.update_job(job)
            self.update_state(state='FAILURE', meta={
                'status': 'timeout',
                'job_id': job_id,
                'error': job.error_message,
                'progress': job.progress
            })
            raise Ignore()
            
    except WorkerLostError as worker_lost_err:
        error_msg = f"Worker perdido durante processamento (provável OOM): {str(worker_lost_err)}"
        logger.critical(f"💀 Job {job_id} WORKER LOST: {error_msg}")
        
        if 'job' in locals():
            job.status = JobStatus.FAILED
            job.error_message = error_msg
            try:
                self.job_store.update_job(job)
            except Exception:
                pass
        
        self.update_state(state='FAILURE', meta={
            'status': 'worker_lost',
            'job_id': job_id,
            'error': error_msg,
            'progress': 0.0
        })
        raise Ignore()
        
    except Ignore:
        raise
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"💥 Erro ao processar job {job_id}: {error_msg}", exc_info=True)
        
        if 'job' in locals():
            job.status = JobStatus.FAILED
            job.error_message = error_msg
            try:
                self.job_store.update_job(job)
            except Exception:
                pass
        
        self.update_state(state='FAILURE', meta={
            'status': 'failed',
            'job_id': job_id,
            'error': error_msg,
            'progress': 0.0
        })
        raise Ignore()



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
