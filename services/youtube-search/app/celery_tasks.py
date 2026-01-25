"""
Celery tasks for YouTube search service
"""
import logging
from typing import Dict, Any
import asyncio
from datetime import datetime

from .celery_config import celery_app
from .models import Job, JobStatus
from .processor import YouTubeSearchProcessor
from .redis_store import RedisJobStore
from .config import get_settings

logger = logging.getLogger(__name__)

# Initialize processor and store
settings = get_settings()
processor = YouTubeSearchProcessor()
redis_url = settings['redis_url']
job_store = RedisJobStore(redis_url=redis_url)

# Inject job_store into processor
processor.job_store = job_store


@celery_app.task(name='youtube_search_task', bind=True)
def youtube_search_task(self, job_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Celery task to process YouTube search job
    
    Args:
        job_dict: Job data dictionary
        
    Returns:
        Updated job dictionary
    """
    job = Job(**job_dict)
    
    try:
        logger.info(f"🚀 Celery worker processing job {job.id}")
        
        # Update job status
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now()  # Marca quando começou
        job_store.update_job(job)
        
        # Process job asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            updated_job = loop.run_until_complete(processor.process_search_job(job))
        finally:
            loop.close()
        
        logger.info(f"✅ Job {job.id} completed by Celery worker")
        return updated_job.model_dump(mode='json')
        
    except Exception as e:
        logger.error(f"❌ Celery worker error for job {job.id}: {e}", exc_info=True)
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job_store.update_job(job)
        return job.model_dump(mode='json')


@celery_app.task(name='cleanup_expired_jobs')
def cleanup_expired_jobs() -> Dict[str, Any]:
    """
    Periodic task to cleanup expired jobs
    
    Returns:
        Cleanup statistics
    """
    try:
        logger.info("🧹 Running periodic cleanup of expired jobs")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            expired_count = loop.run_until_complete(job_store.cleanup_expired())
        finally:
            loop.close()
        
        result = {
            "status": "success",
            "expired_jobs_removed": expired_count
        }
        
        logger.info(f"✅ Cleanup completed: {expired_count} jobs removed")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


# Configure periodic tasks
celery_app.conf.beat_schedule = {
    'cleanup-expired-jobs': {
        'task': 'cleanup_expired_jobs',
        'schedule': 1800.0,  # Every 30 minutes
    },
}
