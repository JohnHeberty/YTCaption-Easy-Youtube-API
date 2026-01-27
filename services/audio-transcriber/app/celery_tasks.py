import os
import logging
import asyncio
from datetime import datetime, timedelta
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
    import traceback
    import sys
    
    job_id = job_dict.get('id', 'unknown')
    retry_count = self.request.retries
    logger.info(f"🚀 Iniciando transcrição do job {job_id} (tentativa {retry_count + 1}/{self.max_retries + 1})")
    
    job = None
    
    try:
        # Reconstitui job
        try:
            job = Job(**job_dict)
            logger.info(f"✅ Job {job_id} reconstituído com sucesso")
        except ValidationError as ve:
            logger.error(f"❌ Erro de validação ao reconstituir job {job_id}: {ve}")
            
            # Tenta marcar job como FAILED no Redis
            try:
                redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
                store = RedisJobStore(redis_url=redis_url)
                
                # Cria job mínimo com erro
                minimal_job = Job(
                    id=job_id,
                    status=JobStatus.FAILED,
                    error_message=f"Schema inválido: {str(ve)}. Job precisa ser recriado com schema atualizado.",
                    input_file=job_dict.get('input_file', 'unknown'),
                    operation=job_dict.get('operation', 'transcribe'),
                    created_at=datetime.now(),
                    received_at=datetime.now(),
                    expires_at=datetime.now() + timedelta(hours=24)
                )
                store.save_job(minimal_job)
                logger.info(f"✅ Job {job_id} marcado como FAILED por schema inválido")
            except Exception as store_err:
                logger.error(f"❌ Não foi possível marcar job {job_id} como FAILED: {store_err}")
            
            # Não usa update_state que causa problemas de serialização
            raise Ignore()
        
        # Atualiza status
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now()  # Marca quando começou
        job.progress = 0.0
        self.job_store.update_job(job)
        
        # Processa transcrição
        try:
            result_job = self.processor.transcribe_audio(job)
            self.job_store.update_job(result_job)
            
            logger.info(f"✅ Job {job_id} concluído: {result_job.status}")
            
            if result_job.status == JobStatus.COMPLETED:
                return result_job.model_dump()
            else:
                # Job falhou no processor
                logger.error(f"❌ Job {job_id} falhou: {result_job.error_message}")
                raise Ignore()
            
        except SoftTimeLimitExceeded:
            logger.error(f"⏰ Job {job_id} excedeu soft time limit")
            job.status = JobStatus.FAILED
            job.error_message = "Transcrição excedeu o tempo limite (45 minutos)"
            job.progress = 0.0
            self.job_store.update_job(job)
            raise Ignore()
            
    except WorkerLostError as worker_lost_err:
        error_msg = f"Worker perdido durante processamento (provável OOM): {str(worker_lost_err)}"
        logger.critical(f"💀 Job {job_id} WORKER LOST: {error_msg}")
        
        if job:
            job.status = JobStatus.FAILED
            job.error_message = error_msg
            job.progress = 0.0
            try:
                self.job_store.update_job(job)
            except Exception as store_err:
                logger.error(f"Erro ao atualizar Redis: {store_err}")
        
        raise Ignore()
        
    except Ignore:
        # Re-raise Ignore sem processar
        raise
        
    except Exception as e:
        # Captura todas as outras exceções
        exc_type, exc_value, exc_tb = sys.exc_info()
        error_msg = str(e)
        error_traceback = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
        
        logger.error(f"💥 Erro ao processar job {job_id}: {error_msg}")
        logger.error(f"Traceback:\n{error_traceback}")
        
        if job:
            job.status = JobStatus.FAILED
            job.error_message = error_msg
            job.progress = 0.0
            try:
                self.job_store.update_job(job)
            except Exception as store_err:
                logger.error(f"Erro ao atualizar Redis: {store_err}")
        
        # Usa Ignore para evitar problemas de serialização do Celery
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


@celery_app.task(name='cleanup_orphan_jobs')
def cleanup_orphan_jobs_task():
    """
    Task para limpar jobs órfãos periodicamente.
    Deve ser agendada com Celery Beat ou executada manualmente.
    """
    logger.info("🧹 Executando limpeza de jobs órfãos")
    
    from .orphan_cleaner import OrphanJobCleaner
    
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    store = RedisJobStore(redis_url=redis_url)
    cleaner = OrphanJobCleaner(store)
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    stats = loop.run_until_complete(cleaner.cleanup_orphans())
    
    logger.info(
        f"✅ Limpeza de órfãos concluída: {stats['orphans_found']} órfãos, "
        f"{stats['requeued']} reenfileirados, {stats['failed']} falhados"
    )
    
    return {"status": "completed", "stats": stats}
