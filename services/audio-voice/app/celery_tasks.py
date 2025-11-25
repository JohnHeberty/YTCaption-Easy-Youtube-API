"""
Tarefas Celery para processamento assíncrono
"""
import asyncio
import logging

from .celery_config import celery_app
from .models import Job, VoiceProfile
from .processor import VoiceProcessor
from .redis_store import RedisJobStore
from .config import get_settings

logger = logging.getLogger(__name__)

# Inicializa store e processor
settings = get_settings()
job_store = RedisJobStore(redis_url=settings['redis_url'])
processor = VoiceProcessor()
processor.job_store = job_store


def run_async_task(coro):
    """
    Helper para executar corrotina async em task Celery síncrona
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, name='app.celery_tasks.dubbing_task')
def dubbing_task(self, job_dict: dict):
    """
    Task Celery para processar dublagem
    
    Args:
        job_dict: Job serializado como dict
    """
    async def _process():
        try:
            # Reconstrói job
            job = Job(**job_dict)
            logger.info(f"🎬 Celery dubbing task started for job {job.id}")
            
            # Busca voice profile se necessário
            voice_profile = None
            if job.voice_id:
                voice_profile = job_store.get_voice_profile(job.voice_id)
                if not voice_profile:
                    raise ValueError(f"Voice profile not found: {job.voice_id}")
            
            # Processa
            job = await processor.process_dubbing_job(job, voice_profile)
            
            logger.info(f"✅ Celery dubbing task completed for job {job.id}")
            return {"status": "completed", "job_id": job.id}
            
        except Exception as e:
            logger.error(f"❌ Celery dubbing task failed: {e}", exc_info=True)
            # Atualiza job como falho
            try:
                from .models import JobStatus
                job = Job(**job_dict)
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job_store.update_job(job)
            except Exception as update_err:
                logger.error(f"Failed to update job status: {update_err}")
            raise
    
    return run_async_task(_process())


@celery_app.task(bind=True, name='app.celery_tasks.clone_voice_task')
def clone_voice_task(self, job_dict: dict):
    """
    Task Celery para processar clonagem de voz
    
    Args:
        job_dict: Job serializado como dict
    """
    async def _process():
        try:
            # Reconstrói job
            job = Job(**job_dict)
            logger.info(f"🎤 Celery clone voice task started for job {job.id}")
            
            # Processa
            voice_profile = await processor.process_clone_job(job)
            
            logger.info(f"✅ Celery clone voice task completed: {voice_profile.id}")
            return {"status": "completed", "voice_id": voice_profile.id}
            
        except Exception as e:
            logger.error(f"❌ Celery clone voice task failed: {e}", exc_info=True)
            # Atualiza job como falho
            try:
                from .models import JobStatus
                job = Job(**job_dict)
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job_store.update_job(job)
            except Exception as update_err:
                logger.error(f"Failed to update job status: {update_err}")
            raise
    
    return run_async_task(_process())
