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
    Task ULTRA-RESILIENTE do Celery para normalização de áudio.
    GARANTIA ABSOLUTA: Esta task NUNCA derruba a API - TODAS as exceções são capturadas e tratadas.
    
    Args:
        job_dict (dict): Job serializado como dicionário.
    Returns:
        dict: Job atualizado como dicionário com status success/failure.
    """
    from celery.exceptions import Ignore
    
    job_id = job_dict.get('id', 'unknown')
    logger.info(f"🚀 Task iniciada para job {job_id}")
    
    try:
        # 1. RECONSTITUIÇÃO DO JOB - PRIMEIRA LINHA DE DEFESA
        try:
            job = Job(**job_dict)
            logger.info(f"✅ Job {job_id} reconstitution successful")
        except ValidationError as ve:
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
            
            # PROCESSAMENTO REAL COM TIMEOUT DE SEGURANÇA
            async def process_with_timeout():
                return await self.processor.process_audio_job(job)
            
            # Timeout de 15 minutos para evitar jobs infinitos
            try:
                logger.info(f"⏱️ Starting processing with 15min timeout for job {job_id}")
                loop.run_until_complete(asyncio.wait_for(process_with_timeout(), timeout=900))
                
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
                logger.error(f"⏰ Job {job_id} TIMEOUT after 15 minutes")
                job.status = JobStatus.FAILED
                job.error_message = "Processing timeout - job exceeded 15 minutes limit"
            except Exception as process_inner_err:
                logger.error(f"💥 Job {job_id} inner processing exception: {process_inner_err}", exc_info=True)
                job.status = JobStatus.FAILED
                job.error_message = f"Processing exception: {str(process_inner_err)}"
                
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
