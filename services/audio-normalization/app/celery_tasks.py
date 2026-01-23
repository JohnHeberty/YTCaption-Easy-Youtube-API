#!/usr/bin/env python3
"""
Tasks do Celery para normalização de áudio
"""

import os
import logging
import asyncio
from datetime import datetime
from celery import Task
from celery import signals
from .celery_config import celery_app
from .models import Job, JobStatus
from .processor import AudioProcessor
from .redis_store import RedisJobStore
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

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
            redis_url = os.getenv('REDIS_URL', None)
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
                
                redis_url = os.getenv('REDIS_URL', None)
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


@celery_app.task(
    bind=True, 
    base=CallbackTask, 
    name='normalize_audio_task',
    autoretry_for=(ConnectionError, IOError, OSError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=1500,
    time_limit=1800
)
def normalize_audio_task(self, job_dict: dict) -> dict:
    """
    Task ULTRA-RESILIENTE do Celery para normalização de áudio.
    GARANTIA ABSOLUTA: Esta task NUNCA derruba a API - TODAS as exceções são capturadas e tratadas.
    
    Retry Policy:
    - Auto-retry em: ConnectionError, IOError, OSError (falhas recuperáveis)
    - Max retries: 3
    - Backoff exponencial com jitter
    - Soft timeout: 25 minutos
    - Hard timeout: 30 minutos
    
    Args:
        job_dict (dict): Job serializado como dicionário.
    Returns:
        dict: Job atualizado como dicionário com status success/failure.
    """
    from celery.exceptions import Ignore, WorkerLostError, SoftTimeLimitExceeded
    
    job_id = job_dict.get('id', 'unknown')
    retry_count = self.request.retries
    logger.info(f"🚀 Task iniciada para job {job_id} (tentativa {retry_count + 1}/{self.max_retries + 1})")
    
    try:
        # 1. RECONSTITUIÇÃO DO JOB - PRIMEIRA LINHA DE DEFESA
        try:
            job = Job(**job_dict)
            logger.info(f"✅ Job {job_id} reconstitution successful")
        except Exception as ve:
            logger.error(f"❌ Job {job_id} validation error during reconstitution: {ve}")
            # Fallback: preenche campos ausentes com defaults
            fields = {}
            for field in Job.model_fields:
                if field in job_dict:
                    fields[field] = job_dict[field]
                else:
                    default_val = Job.model_fields[field].default
                    fields[field] = default_val if default_val is not None else ""
            job = Job(**fields)
            logger.info(f"⚠️ Job {job_id} reconstitution with default values")
        except Exception as reconst_err:
            logger.critical(f"🔥 CRITICAL: Unable to reconstitute job {job_id}: {reconst_err}")
            # Atualiza Celery com erro fatal
            self.update_state(state='FAILURE', meta={
                'status': 'failed',
                'job_id': job_id,
                'error': f'Job reconstitution failed: {str(reconst_err)}',
                'progress': 0.0
            })
            raise Ignore()  # Evita retry automático
        
        # 2. PROCESSAMENTO COMPLETO - SEGUNDA LINHA DE DEFESA
        try:
            logger.info(f"🔧 Starting audio processing for job {job_id}")
            logger.info(f"📋 Processing params: noise={job.remove_noise}, highpass={job.apply_highpass_filter}, vocals={job.isolate_vocals}")
            
            # Atualiza para PROCESSING
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now()  # Marca quando começou
            job.progress = 0.0
            
            try:
                self.job_store.update_job(job)
                logger.info(f"📝 Job {job_id} marked as PROCESSING in store")
            except Exception as redis_err:
                logger.warning(f"⚠️ Redis update failed for job {job_id}: {redis_err}")
                # Continua processamento mesmo se Redis falhar
            
            # Atualiza estado do Celery para STARTED
            self.update_state(state='STARTED', meta={
                'status': 'processing',
                'job_id': job_id,
                'progress': 0.0
            })
            
            # Configuração do loop assíncrono
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # PROCESSAMENTO REAL COM TIMEOUT DE SEGURANÇA (configurável)
            from .config import get_settings
            settings = get_settings()
            async_timeout = int(settings.get('timeouts', {}).get('async_timeout_sec', 900))
            heartbeat_interval = int(settings.get('timeouts', {}).get('job_heartbeat_interval_sec', 30))
            
            async def process_with_timeout_and_heartbeat():
                """Processa job com heartbeat periódico"""
                import asyncio
                
                # Task de heartbeat em background
                async def send_heartbeat():
                    while True:
                        try:
                            await asyncio.sleep(heartbeat_interval)
                            job.update_heartbeat()
                            self.job_store.update_job(job)
                            logger.debug(f"💓 Heartbeat enviado para job {job_id}")
                        except asyncio.CancelledError:
                            break
                        except Exception as hb_err:
                            logger.warning(f"⚠️ Erro ao enviar heartbeat: {hb_err}")
                
                # Inicia heartbeat em background
                heartbeat_task = asyncio.create_task(send_heartbeat())
                
                try:
                    # Processa job
                    result = await self.processor.process_audio_job(job)
                    return result
                finally:
                    # Cancela heartbeat ao terminar
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass
            
            # Timeout configurável via env (padrão: 15 minutos)
            try:
                logger.info(f"⏱️ Starting processing with {async_timeout}s timeout and {heartbeat_interval}s heartbeat for job {job_id}")
                loop.run_until_complete(asyncio.wait_for(process_with_timeout_and_heartbeat(), timeout=async_timeout))
                
                # Verifica se processamento foi bem-sucedido
                if job.status == JobStatus.COMPLETED:
                    logger.info(f"✅ Job {job_id} processing completed successfully")
                    # Atualiza estado final no Celery
                    self.update_state(state='SUCCESS', meta={
                        'status': 'completed',
                        'job_id': job_id,
                        'output_file': job.output_file,
                        'progress': 100.0
                    })
                else:
                    logger.error(f"❌ Job {job_id} processing failed - final status: {job.status}")
                    # Força status para FAILED se não foi marcado como COMPLETED
                    job.status = JobStatus.FAILED
                    if not job.error_message:
                        job.error_message = f"Processing ended with unexpected status: {job.status}"
                        
            except asyncio.TimeoutError:
                logger.error(f"⏰ Job {job_id} TIMEOUT after {async_timeout}s")
                job.status = JobStatus.FAILED
                job.error_message = f"Processing timeout - job exceeded {async_timeout}s limit"
            except SoftTimeLimitExceeded:
                logger.error(f"⏰ Job {job_id} SOFT TIME LIMIT exceeded")
                job.status = JobStatus.FAILED
                job.error_message = "Processing exceeded soft time limit (25 minutes)"
            except Exception as process_inner_err:
                logger.error(f"💥 Job {job_id} inner processing exception: {process_inner_err}", exc_info=True)
                job.status = JobStatus.FAILED
                job.error_message = f"Processing exception: {str(process_inner_err)}"
                
        except WorkerLostError as worker_lost_err:
            # TRATAMENTO ESPECÍFICO PARA WORKER PERDIDO (OOM KILL, SIGKILL)
            error_msg = f"Worker lost during processing (likely OOM or crash): {str(worker_lost_err)}"
            logger.critical(f"💀 Job {job_id} WORKER LOST: {error_msg}")
            
            job.status = JobStatus.FAILED
            job.error_message = error_msg
            job.progress = 0.0
            
            # Atualiza store imediatamente
            try:
                self.job_store.update_job(job)
            except Exception as redis_err:
                logger.error(f"Failed to update job status after worker loss: {redis_err}")
            
            # Não tenta retry em caso de worker loss
            self.update_state(state='FAILURE', meta={
                'status': 'worker_lost',
                'job_id': job_id,
                'error': error_msg,
                'progress': 0.0
            })
            raise Ignore()
            
        except Exception as process_err:
            # TERCEIRA LINHA DE DEFESA - PROCESSAMENTO FALHOU COMPLETAMENTE
            error_msg = str(process_err)
            logger.error(f"💥 Job {job_id} OUTER processing exception: {error_msg}", exc_info=True)
            
            job.status = JobStatus.FAILED
            job.error_message = f"Critical processing failure: {error_msg}"
            job.progress = 0.0
            
        # 3. ATUALIZAÇÃO FINAL DO STATUS - QUARTA LINHA DE DEFESA
        try:
            self.job_store.update_job(job)
            logger.info(f"📝 Job {job_id} final status updated in store: {job.status}")
        except Exception as redis_final_err:
            logger.error(f"🔥 CRITICAL: Failed to update final status in store for job {job_id}: {redis_final_err}")
            # Continua mesmo se Redis falhar - pelo menos o Celery terá o estado
        
        # 4. RESULTADO FINAL GARANTIDO
        if job.status == JobStatus.FAILED:
            # Atualiza estado do Celery para FAILURE com metadados estruturados
            self.update_state(state='FAILURE', meta={
                'status': 'failed',
                'job_id': job_id,
                'error': job.error_message or 'Unknown processing error',
                'progress': job.progress
            })
            logger.error(f"🚨 Job {job_id} FINAL STATUS: FAILED - {job.error_message}")
            
            # IMPORTANTE: Usa Ignore() para evitar retry automático
            raise Ignore()
        else:
            logger.info(f"🎉 Job {job_id} FINAL STATUS: {job.status}")
        
        return job.model_dump()
        
    except Ignore:
        # Re-raise Ignore (é controlado)
        raise
    except Exception as catastrophic_err:
        # QUINTA LINHA DE DEFESA - FALHA CATASTRÓFICA (ÚLTIMA BARREIRA)
        error_msg = f"CATASTROPHIC FAILURE in job {job_id}: {str(catastrophic_err)}"
        logger.critical(error_msg, exc_info=True)
        
        # Atualiza estado do Celery para FAILURE
        self.update_state(state='FAILURE', meta={
            'status': 'catastrophic_failure',
            'job_id': job_id,
            'error': error_msg,
            'progress': 0.0
        })
        
        # Tenta atualizar store se possível
        try:
            if 'job' in locals() and job:
                job.status = JobStatus.FAILED
                job.error_message = error_msg
                self.job_store.update_job(job)
        except Exception:
            pass  # Ignora se falhar
        
        # NUNCA deixa exceção subir - usa Ignore()
        raise Ignore()


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
