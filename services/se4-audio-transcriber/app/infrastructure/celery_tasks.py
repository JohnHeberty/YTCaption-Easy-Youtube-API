from __future__ import annotations

import os
import asyncio
from datetime import datetime, timedelta
from typing import Any
from common.datetime_utils import now_brazil

from celery import Task
from celery import signals
from ..domain.models import Job, JobStatus
from ..services.processor import TranscriptionProcessor
from ..infrastructure.redis_store import RedisJobStore
from .celery_config import celery_app
from common.log_utils import get_logger

logger = get_logger(__name__)


def _update_job_failed(job_dict: dict, error_message: str) -> None:
    """Helper shared by signal handlers to mark a job as FAILED in Redis."""
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    store = RedisJobStore(redis_url=redis_url)

    try:
        job_id = job_dict.get('id', 'unknown')
        job = Job(**job_dict)
        job.status = JobStatus.FAILED
        job.error_message = error_message
        job.completed_at = now_brazil()
        job.updated_at = now_brazil()
        job.progress = 0.0

        store.update_job(job)
        logger.info(f"✅ SIGNAL: Updated Redis Store for failed job {job_id}")
    except Exception as update_err:
        logger.error(f"❌ SIGNAL: Failed to update Redis Store: {update_err}")


# ==========================================
# SIGNAL HANDLERS PARA SINCRONIZAÇÃO REDIS
# ==========================================

@signals.task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **kw):
    """Signal handler disparado quando uma task falha."""
    logger.error(f"🔴 SIGNAL: Task failure detected for task_id={task_id}, exception={exception}")

    try:
        if args and len(args) > 0 and isinstance(args[0], dict):
            _update_job_failed(args[0], f"Task failed: {str(exception)}")
    except Exception as handler_err:
        logger.error(f"❌ SIGNAL HANDLER ERROR: {handler_err}")


@signals.task_revoked.connect
def task_revoked_handler(sender=None, request=None, terminated=None, signum=None, expired=None, **kw):
    """Signal handler disparado quando uma task é revogada (killed, canceled)."""
    task_id = request.id if request else 'unknown'
    logger.error(f"🔴 SIGNAL: Task revoked task_id={task_id}, terminated={terminated}, signum={signum}")

    try:
        if request and hasattr(request, 'args') and request.args and len(request.args) > 0:
            job_dict = request.args[0]
            if isinstance(job_dict, dict):
                _update_job_failed(job_dict, f"Task revoked: terminated={terminated}, signal={signum}")
    except Exception as handler_err:
        logger.error(f"❌ SIGNAL HANDLER ERROR: {handler_err}")

class TranscriptionTask(Task):
    def __init__(self) -> None:
        self._processor = None
        self._job_store = None

    @property
    def processor(self) -> TranscriptionProcessor:
        if self._processor is None:
            self._processor = TranscriptionProcessor(
                output_dir=os.getenv("WHISPER_OUTPUT_DIR", "./transcriptions"),
                model_dir=os.getenv("WHISPER_MODEL_DIR", "./models")
            )
            if self._job_store:
                self._processor.job_store = self._job_store
        return self._processor

    @property
    def job_store(self) -> RedisJobStore:
        if self._job_store is None:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self._job_store = RedisJobStore(redis_url=redis_url)
            if self._processor:
                self._processor.job_store = self._job_store
        return self._job_store

def _reconstruct_job(job_dict: dict[str, Any], job_id: str) -> Job | None:
    """Reconstruct a Job from a serialized dict. Returns None and marks FAILED on error."""
    from pydantic import ValidationError

    try:
        job = Job(**job_dict)
        logger.info(f"✅ Job {job_id} reconstituído com sucesso")
        return job
    except ValidationError as ve:
        logger.error(f"❌ Erro de validação ao reconstituir job {job_id}: {ve}")
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            store = RedisJobStore(redis_url=redis_url)
            minimal_job = Job(
                id=job_id,
                status=JobStatus.FAILED,
                error_message=f"Schema inválido: {str(ve)}. Job precisa ser recriado com schema atualizado.",
                input_file=job_dict.get('input_file', 'unknown'),
                operation=job_dict.get('operation', 'transcribe'),
                created_at=now_brazil(),
                received_at=now_brazil(),
                expires_at=now_brazil() + timedelta(hours=24),
            )
            store.save_job(minimal_job)
            logger.info(f"✅ Job {job_id} marcado como FAILED por schema inválido")
        except Exception as store_err:
            logger.error(f"❌ Não foi possível marcar job {job_id} como FAILED: {store_err}")
        return None


def _mark_job_failed(job: Job, error_msg: str, store: RedisJobStore) -> None:
    """Mark a job as FAILED in Redis with the given error message."""
    job.status = JobStatus.FAILED
    job.error_message = error_msg
    job.completed_at = now_brazil()
    job.updated_at = now_brazil()
    job.progress = 0.0
    try:
        store.update_job(job)
    except Exception as store_err:
        logger.error(f"Erro ao atualizar Redis: {store_err}")

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
def transcribe_audio_task(self, job_dict: dict[str, Any]) -> None:
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
    import traceback
    import sys
    
    job_id = job_dict.get('id', 'unknown')
    retry_count = self.request.retries
    logger.info(f"🚀 Iniciando transcrição do job {job_id} (tentativa {retry_count + 1}/{self.max_retries + 1})")
    
    job = None
    
    try:
        job = _reconstruct_job(job_dict, job_id)
        if job is None:
            raise Ignore()
        
        job.status = JobStatus.PROCESSING
        job.started_at = now_brazil()
        job.updated_at = now_brazil()
        job.progress = 0.0
        self.job_store.update_job(job)
        
        try:
            result_job = self.processor.transcribe_audio(job)
            self.job_store.update_job(result_job)
            
            logger.info(f"✅ Job {job_id} concluído: {result_job.status}")
            
            if result_job.status == JobStatus.COMPLETED:
                return result_job.model_dump()
            else:
                logger.error(f"❌ Job {job_id} falhou: {result_job.error_message}")
                raise Ignore()
            
        except SoftTimeLimitExceeded:
            logger.error(f"⏰ Job {job_id} excedeu soft time limit")
            _mark_job_failed(job, "Transcrição excedeu o tempo limite (45 minutos)", self.job_store)
            raise Ignore()
            
    except WorkerLostError as worker_lost_err:
        error_msg = f"Worker perdido durante processamento (provável OOM): {str(worker_lost_err)}"
        logger.critical(f"💀 Job {job_id} WORKER LOST: {error_msg}")
        if job:
            _mark_job_failed(job, error_msg, self.job_store)
        raise Ignore()
        
    except Ignore:
        raise
        
    except Exception as e:
        exc_type, exc_value, exc_tb = sys.exc_info()
        error_msg = str(e)
        error_traceback = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
        
        logger.error(f"💥 Erro ao processar job {job_id}: {error_msg}")
        logger.error(f"Traceback:\n{error_traceback}")
        
        if job:
            _mark_job_failed(job, error_msg, self.job_store)
        
        raise Ignore()

@celery_app.task(name='cleanup_expired_jobs')
def cleanup_expired_jobs_task() -> dict[str, Any]:
    logger.info("Executando limpeza de jobs expirados")
    
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    store = RedisJobStore(redis_url=redis_url)
    
    expired = store.cleanup_expired()
    
    return {"status": "completed", "expired_jobs": expired}

@celery_app.task(name='cleanup_orphan_jobs')
def cleanup_orphan_jobs_task() -> dict[str, Any]:
    """
    Task para limpar jobs órfãos periodicamente.
    Deve ser agendada com Celery Beat ou executada manualmente.
    """
    logger.info("🧹 Executando limpeza de jobs órfãos")
    
    from app.shared.orphan_cleaner import OrphanJobCleaner
    
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
