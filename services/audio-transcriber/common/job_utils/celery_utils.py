"""
Standard Celery task utilities with fallback support.

Provides a unified pattern for submitting jobs to Celery workers
with automatic fallback to async processing when Celery is unavailable,
and a callback base class for consistent task lifecycle management.
"""
import asyncio
import logging
from typing import Any, Callable, Optional
from datetime import datetime

from celery import Task

from common.job_utils.models import StandardJob, JobStatus
from common.job_utils.manager import JobManager

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """
    Base Celery task that provides automatic job status updates
    on task start, success, and failure.

    Expects job_id as the first argument of the task.
    The associated JobManager must be set as `job_manager` on the class.
    """

    job_manager: Optional[JobManager] = None

    def on_success(self, retval, task_id, args, kwargs):
        if not self.job_manager:
            return
        try:
            job_id = args[0] if args else kwargs.get("job_id")
            if job_id:
                self.job_manager.complete_job(job_id, message="Task completed successfully")
        except Exception as e:
            logger.error(f"CallbackTask on_success error: {e}")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        if not self.job_manager:
            return
        try:
            job_id = args[0] if args else kwargs.get("job_id")
            if job_id:
                self.job_manager.fail_job(
                    job_id,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
        except Exception as e:
            logger.error(f"CallbackTask on_failure error: {e}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        if not self.job_manager:
            return
        try:
            job_id = args[0] if args else kwargs.get("job_id")
            if job_id:
                job = self.job_manager.get_job_optional(job_id)
                if job:
                    job.increment_retry()
                    job.progress_message = f"Retrying: {str(exc)}"
                    self.job_manager.update_job(job)
        except Exception as e:
            logger.error(f"CallbackTask on_retry error: {e}")


def submit_task(
    celery_app,
    task_name: str,
    job_id: str,
    job_data: dict,
    *,
    celery_available: bool = True,
    fallback_fn: Optional[Callable] = None,
    task_kwargs: Optional[dict] = None,
) -> dict:
    """
    Submit a task to Celery with optional fallback to async processing.

    Args:
        celery_app: The Celery application instance.
        task_name: Name of the registered Celery task.
        job_id: The job ID for tracking.
        job_data: Serialized job data to pass to the worker.
        celery_available: Whether Celery is available (from health check).
        fallback_fn: Async function to call if Celery is unavailable.
        task_kwargs: Additional kwargs for apply_async.

    Returns:
        dict with 'submitted' (bool), 'method' (str), 'task_id' or 'error'.
    """
    async_kwargs = task_kwargs or {}
    async_kwargs["task_id"] = job_id

    if celery_available:
        try:
            result = celery_app.send_task(
                task_name,
                args=[job_data],
                kwargs=async_kwargs,
            )
            if not result:
                raise ConnectionError("Celery returned no result (broker may be down)")
            logger.info(f"Job {job_id} submitted to Celery task {task_name}")
            return {
                "submitted": True,
                "method": "celery",
                "task_id": result.id,
            }
        except Exception as e:
            logger.warning(f"Celery submission failed for {job_id}: {e}")
            if fallback_fn is None:
                raise
            logger.info(f"Falling back to async processing for job {job_id}")

    if fallback_fn is not None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(fallback_fn(job_data))
            else:
                loop.run_until_complete(fallback_fn(job_data))
            logger.info(f"Job {job_id} submitted to async fallback")
            return {
                "submitted": True,
                "method": "async_fallback",
                "task_id": None,
            }
        except Exception as e:
            logger.error(f"Async fallback also failed for {job_id}: {e}")
            raise

    raise ConnectionError(f"Cannot submit job {job_id}: Celery unavailable and no fallback provided")


def reconstitute_job(job_data: dict) -> StandardJob:
    """Reconstitute a StandardJob from serialized dict for use in Celery tasks."""
    return StandardJob.model_validate(job_data)


def serialize_job(job: StandardJob) -> dict:
    """Serialize a StandardJob to dict for passing to Celery tasks."""
    return job.model_dump(mode="json")