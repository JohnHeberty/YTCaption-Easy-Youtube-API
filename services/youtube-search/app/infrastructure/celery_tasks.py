"""
Celery tasks for YouTube search service.

Implements async task processing with timeouts and retry policies.
"""
from typing import Dict, Any
import asyncio

from celery import signals
from celery.exceptions import SoftTimeLimitExceeded

from .celery_config import celery_app
from ..core.constants import (
    CELERY_TASK_TIMEOUT_SECONDS,
    CELERY_TASK_MAX_RETRIES,
    CELERY_TASK_RETRY_DELAY_SECONDS,
)
from app.domain.models import Job, JobStatus
from ..domain.processor import YouTubeSearchProcessor
from .redis_store import YouTubeSearchJobStore as RedisJobStore
from ..core.config import get_settings
from common.datetime_utils import now_brazil
from common.log_utils import get_logger

logger = get_logger(__name__)

@signals.task_failure.connect
def task_failure_handler(task_id, exception, args, kwargs, traceback, einfo, **kw):
    """Log Celery worker failures with full context."""
    logger.error(
        "Celery task_failure | task_id=%s error=%s",
        task_id, exception, exc_info=einfo.exc_info if einfo else None
    )

# Initialize processor and store
settings = get_settings()
processor = YouTubeSearchProcessor()
redis_url = settings['redis_url']
job_store = RedisJobStore(redis_url=redis_url)

# Inject job_store into processor
processor.job_store = job_store

@celery_app.task(
    name='youtube_search_task',
    bind=True,
    time_limit=CELERY_TASK_TIMEOUT_SECONDS + 30,  # Hard limit
    soft_time_limit=CELERY_TASK_TIMEOUT_SECONDS,  # Soft limit (can catch)
    max_retries=CELERY_TASK_MAX_RETRIES,
    default_retry_delay=CELERY_TASK_RETRY_DELAY_SECONDS,
)
def youtube_search_task(self, job_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Celery task to process YouTube search job.

    Args:
        job_dict: Job data dictionary

    Returns:
        Updated job dictionary

    Timeouts:
        - Soft time limit: 300 seconds (5 minutes) - can be caught
        - Hard time limit: 330 seconds (5.5 minutes) - kills task
    """
    job = Job(**job_dict)

    try:
        logger.info(f"🚀 Celery worker processing job {job.id}")

        # Update job status
        job.status = JobStatus.PROCESSING
        job.started_at = now_brazil()
        job_store.update_job(job)

        # Process job asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            updated_job = loop.run_until_complete(
                processor.process_search_job(job)
            )
        finally:
            loop.close()

        logger.info(f"✅ Job {job.id} completed by Celery worker")
        return updated_job.model_dump(mode='json')

    except SoftTimeLimitExceeded:
        logger.error(f"⏱️ Soft time limit exceeded for job {job.id}")
        job.status = JobStatus.FAILED
        job.error_message = f"Task timed out after {CELERY_TASK_TIMEOUT_SECONDS}s"
        job_store.update_job(job)

        # Retry if we haven't exceeded max retries
        try:
            raise self.retry(
                exc=TimeoutError(f"Task timed out after {CELERY_TASK_TIMEOUT_SECONDS}s"),
                countdown=CELERY_TASK_RETRY_DELAY_SECONDS * (self.request.retries + 1),
            )
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for job {job.id}")
            return job.model_dump(mode='json')

    except Exception as e:
        logger.error(f"❌ Celery worker error for job {job.id}: {e}", exc_info=True)
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job_store.update_job(job)
        return job.model_dump(mode='json')

@celery_app.task(
    name='cleanup_expired_jobs',
    time_limit=60,  # 1 minute
)
def cleanup_expired_jobs() -> Dict[str, Any]:
    """
    Periodic task to cleanup expired jobs.

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
            "expired_jobs_removed": expired_count,
            "timestamp": now_brazil().isoformat(),
        }

        logger.info(f"✅ Cleanup completed: {expired_count} jobs removed")
        return result

    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "timestamp": now_brazil().isoformat(),
        }

# Configure periodic tasks
celery_app.conf.beat_schedule = {
    'cleanup-expired-jobs': {
        'task': 'cleanup_expired_jobs',
        'schedule': 1800.0,  # Every 30 minutes
        'options': {
            'expires': 60,  # Task expires after 1 minute
        },
    },
}
