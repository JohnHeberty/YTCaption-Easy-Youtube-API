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


@celery_app.task(bind=True, base=CallbackTask, name='normalize_audio_task')
def normalize_audio_task(self, job_dict: dict) -> dict:
    """
    Task RESILIENTE do Celery para normalização de áudio.
    GARANTIA: Esta task NUNCA derruba a API - todas as exceções são tratadas.
    
    Args:
        job_dict (dict): Job serializado como dicionário.
    Returns:
        dict: Job atualizado como dicionário com status success/failure.
    """
    job_id = job_dict.get('id', 'unknown')
    
    try:
        # 1. RECONSTITUIÇÃO DO JOB - PRIMEIRA LINHA DE DEFESA
        try:
            job = Job(**job_dict)
            logger.info(f"✅ Job {job_id} reconstitution successful")
        except ValidationError as ve:
            logger.error(f"❌ Job {job_id} validation error: {ve}")
            # Fallback: preenche campos ausentes
            fields = {}
            for field in Job.model_fields:
                if field in job_dict:
                    fields[field] = job_dict[field]
                else:
                    default_val = Job.model_fields[field].default
                    fields[field] = default_val if default_val is not None else ""
            job = Job(**fields)
            logger.info(f"⚠️ Job {job_id} reconstitution with defaults")
        
        # 2. PROCESSAMENTO COMPLETO - SEGUNDA LINHA DE DEFESA
        try:
            logger.info(f"🔧 Starting audio processing for job {job_id}")
            
            # Atualiza para PROCESSING
            job.status = JobStatus.PROCESSING
            job.progress = 0.0
            
            try:
                self.job_store.update_job(job)
                logger.info(f"📝 Job {job_id} marked as PROCESSING")
            except Exception as redis_err:
                logger.warning(f"⚠️ Redis update failed for job {job_id}: {redis_err}")
                # Continua processamento mesmo se Redis falhar
            
            # Configuração do loop assíncrono
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # PROCESSAMENTO REAL COM TIMEOUT DE SEGURANÇA
            import asyncio
            
            async def process_with_timeout():
                return await self.processor.process_audio_job(job)
            
            # Timeout de 10 minutos para evitar jobs infinitos
            try:
                loop.run_until_complete(asyncio.wait_for(process_with_timeout(), timeout=600))
                
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
                    logger.error(f"❌ Job {job_id} processing failed - status: {job.status}")
                    # Força status para FAILED se não foi marcado como COMPLETED
                    job.status = JobStatus.FAILED
                    if not job.error_message:
                        job.error_message = "Processing completed but status is not COMPLETED"
                        
            except asyncio.TimeoutError:
                logger.error(f"⏰ Job {job_id} timeout after 10 minutes")
                job.status = JobStatus.FAILED
                job.error_message = "Processing timeout - job exceeded 10 minutes"
                
        except Exception as process_err:
            # TERCEIRA LINHA DE DEFESA - PROCESSAMENTO FALHOU
            error_msg = str(process_err)
            logger.error(f"💥 Job {job_id} processing exception: {error_msg}", exc_info=True)
            
            job.status = JobStatus.FAILED
            job.error_message = f"Processing failed: {error_msg}"
            job.progress = 0.0
            
        # 3. ATUALIZAÇÃO FINAL DO STATUS - QUARTA LINHA DE DEFESA
        try:
            self.job_store.update_job(job)
            logger.info(f"📝 Job {job_id} final status updated: {job.status}")
        except Exception as redis_final_err:
            logger.error(f"🔥 CRITICAL: Failed to update final status for job {job_id}: {redis_final_err}")
            # Continua mesmo se Redis falhar - pelo menos o Celery terá o estado
        
        # 4. RESULTADO FINAL GARANTIDO
        if job.status == JobStatus.FAILED:
            # Atualiza estado do Celery para FAILURE com metadados estruturados
            self.update_state(state='FAILURE', meta={
                'status': 'failed',
                'job_id': job_id,
                'error': job.error_message,
                'progress': job.progress
            })
            logger.error(f"🚨 Job {job_id} FINAL STATUS: FAILED - {job.error_message}")
        else:
            logger.info(f"🎉 Job {job_id} FINAL STATUS: {job.status}")
        
        return job.model_dump()
        
    except Exception as catastrophic_err:
        # QUINTA LINHA DE DEFESA - FALHA CATASTRÓFICA
        error_msg = f"CATASTROPHIC FAILURE in job {job_id}: {str(catastrophic_err)}"
        logger.critical(error_msg, exc_info=True)
        
        # Atualiza estado do Celery para FAILURE
        self.update_state(state='FAILURE', meta={
            'status': 'catastrophic_failure',
            'job_id': job_id,
            'error': error_msg,
            'progress': 0.0
        })
        
        # Retorna job falho estruturado
        return {
            'id': job_id,
            'status': 'failed',
            'error_message': error_msg,
            'progress': 0.0
        }


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
