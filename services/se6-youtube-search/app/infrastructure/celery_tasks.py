from __future__ import annotations

"""
Celery tasks for YouTube search service.

Implements async task processing with timeouts and retry policies.
"""
from typing import Any
import asyncio

from celery import signals
from celery.exceptions import SoftTimeLimitExceeded

from .celery_config import celery_app
from ..core.constants import (
    CELERY_TASK_TIMEOUT_SECONDS,
    CELERY_TASK_MAX_RETRIES,
    CELERY_TASK_RETRY_DELAY_SECONDS,
    CELERY_HARD_LIMIT_OFFSET_SECONDS,
    CLEANUP_TASK_TIMEOUT_SECONDS,
    BEAT_SCHEDULE_INTERVAL_SECONDS,
    BEAT_TASK_EXPIRES_SECONDS,
)
from app.domain.models import Job, JobStatus
from ..domain.processor import YouTubeSearchProcessor
from .redis_store import YouTubeSearchJobStore as RedisJobStore
from ..core.config import get_settings
from common.datetime_utils import now_brazil
from common.log_utils import get_logger

logger = get_logger(__name__)

@signals.task_failure.connect
def task_failure_handler(task_id: Any, exception: Any, args: Any, kwargs: Any, traceback: Any, einfo: Any, **kw: Any) -> None:
    """Log Celery worker failures with full context."""
    logger.error(
        "Celery task_failure | task_id=%s error=%s",
        task_id, exception, exc_info=einfo.exc_info if einfo else None
    )

# Lazy initialization — avoids Redis connection at import time
_job_store: RedisJobStore | None = None
_processor: YouTubeSearchProcessor | None = None


def _get_job_store() -> RedisJobStore:
    global _job_store
    if _job_store is None:
        settings = get_settings()
        redis_url = settings['redis_url']
        _job_store = RedisJobStore(redis_url=redis_url)
    return _job_store


def _get_processor() -> YouTubeSearchProcessor:
    global _processor
    if _processor is None:
        _processor = YouTubeSearchProcessor()
        _processor.job_store = _get_job_store()
    return _processor

@celery_app.task(
    name='youtube_search_task',
    bind=True,
    time_limit=CELERY_TASK_TIMEOUT_SECONDS + CELERY_HARD_LIMIT_OFFSET_SECONDS,  # Hard limit
    soft_time_limit=CELERY_TASK_TIMEOUT_SECONDS,  # Soft limit (can catch)
    max_retries=CELERY_TASK_MAX_RETRIES,
    default_retry_delay=CELERY_TASK_RETRY_DELAY_SECONDS,
)
def youtube_search_task(self, job_dict: dict[str, Any]) -> dict[str, Any]:
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
        logger.info("Celery worker processing job %s", job.id)

        # Update job status
        job.status = JobStatus.PROCESSING
        job.started_at = now_brazil()
        _get_job_store().update_job(job)

        # Process job asynchronously
        updated_job = asyncio.run(_get_processor().process_search_job(job))

        logger.info("Job %s completed by Celery worker", job.id)
        return updated_job.model_dump(mode='json')

    except SoftTimeLimitExceeded:
        logger.error("Soft time limit exceeded for job %s", job.id)
        job.status = JobStatus.FAILED
        job.error_message = f"Task timed out after {CELERY_TASK_TIMEOUT_SECONDS}s"
        _get_job_store().update_job(job)

        # Retry if we haven't exceeded max retries
        try:
            raise self.retry(
                exc=TimeoutError(f"Task timed out after {CELERY_TASK_TIMEOUT_SECONDS}s"),
                countdown=CELERY_TASK_RETRY_DELAY_SECONDS * (self.request.retries + 1),
            )
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for job %s", job.id)
            return job.model_dump(mode='json')

    except Exception as e:
        logger.error("Celery worker error for job %s: %s", job.id, e, exc_info=True)
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        _get_job_store().update_job(job)
        return job.model_dump(mode='json')

@celery_app.task(
    name='cleanup_expired_jobs',
    time_limit=CLEANUP_TASK_TIMEOUT_SECONDS,  # 1 minute
)
def cleanup_expired_jobs() -> dict[str, Any]:
    """
    Periodic task to cleanup expired jobs.

    Returns:
        Cleanup statistics
    """
    try:
        logger.info("Running periodic cleanup of expired jobs")

        expired_count = asyncio.run(_get_job_store().cleanup_expired())

        result = {
            "status": "success",
            "expired_jobs_removed": expired_count,
            "timestamp": now_brazil().isoformat(),
        }

        logger.info("Cleanup completed: %s jobs removed", expired_count)
        return result

    except Exception as e:
        logger.error("Error during cleanup: %s", e, exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "timestamp": now_brazil().isoformat(),
        }

# Configure periodic tasks
celery_app.conf.beat_schedule = {
    'cleanup-expired-jobs': {
        'task': 'cleanup_expired_jobs',
        'schedule': BEAT_SCHEDULE_INTERVAL_SECONDS,  # Every 30 minutes
        'options': {
            'expires': BEAT_TASK_EXPIRES_SECONDS,  # Task expires after 1 minute
        },
    },
}
