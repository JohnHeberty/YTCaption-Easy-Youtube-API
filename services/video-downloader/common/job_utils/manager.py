"""
Standard job manager providing CRUD operations and lifecycle management.

Wraps JobRedisStore with business logic for creating, submitting,
updating, and managing job state transitions.
"""
import logging
from typing import Optional

from common.job_utils.models import StandardJob, JobStatus, generate_job_id, generate_random_job_id
from common.job_utils.store import JobRedisStore
from common.job_utils.exceptions import (
    JobNotFoundError,
    JobExpiredError,
    JobCreationError,
)

logger = logging.getLogger(__name__)


class JobManager:
    def __init__(self, store: JobRedisStore):
        self.store = store

    def create_job(
        self,
        id_parts: Optional[list[str]] = None,
        prefix: str = "",
        use_deterministic_id: bool = True,
        correlation_id: Optional[str] = None,
        stages: Optional[list[str]] = None,
        stage_display_names: Optional[dict[str, str]] = None,
    ) -> StandardJob:
        if use_deterministic_id and id_parts:
            job_id = generate_job_id(*id_parts, prefix=prefix)
        else:
            job_id = generate_random_job_id(prefix=prefix)

        job = StandardJob(id=job_id, correlation_id=correlation_id)
        if stages:
            for stage_name in stages:
                display = (stage_display_names or {}).get(stage_name, stage_name)
                job.add_stage(stage_name, display)
        job.mark_as_queued()

        try:
            self.store.save_job(job)
        except Exception as e:
            raise JobCreationError(str(e))

        logger.info(f"Created job {job_id} with status {job.status}")
        return job

    def get_job(self, job_id: str) -> StandardJob:
        job = self.store.get_job(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        if job.is_expired:
            raise JobExpiredError(job_id)
        return job

    def get_job_optional(self, job_id: str) -> Optional[StandardJob]:
        return self.store.get_job(job_id)

    def update_job(self, job: StandardJob) -> StandardJob:
        self.store.update_job(job)
        return job

    def complete_job(self, job_id: str, message: Optional[str] = None) -> StandardJob:
        job = self.get_job(job_id)
        job.mark_as_completed(message)
        self.store.update_job(job)
        logger.info(f"Job {job_id} completed")
        return job

    def fail_job(self, job_id: str, error: str, error_type: Optional[str] = None) -> StandardJob:
        job = self.get_job(job_id)
        job.mark_as_failed(error, error_type)
        self.store.update_job(job)
        logger.error(f"Job {job_id} failed: {error}")
        return job

    def cancel_job(self, job_id: str, reason: Optional[str] = None) -> StandardJob:
        job = self.get_job(job_id)
        job.mark_as_cancelled(reason)
        self.store.update_job(job)
        logger.info(f"Job {job_id} cancelled: {reason}")
        return job

    def start_processing(self, job_id: str, message: Optional[str] = None) -> StandardJob:
        job = self.get_job(job_id)
        job.mark_as_processing(message)
        self.store.update_job(job)
        logger.info(f"Job {job_id} started processing")
        return job

    def update_progress(self, job_id: str, progress: float, message: Optional[str] = None) -> StandardJob:
        job = self.get_job(job_id)
        job.update_progress(progress, message)
        self.store.update_job(job)
        return job

    def start_stage(self, job_id: str, stage_name: str) -> StandardJob:
        job = self.get_job(job_id)
        if stage_name in job.stages:
            job.stages[stage_name].start()
            self.store.update_job(job)
        return job

    def complete_stage(self, job_id: str, stage_name: str, message: Optional[str] = None) -> StandardJob:
        job = self.get_job(job_id)
        if stage_name in job.stages:
            job.stages[stage_name].complete(message)
            job.update_overall_progress()
            self.store.update_job(job)
        return job

    def fail_stage(self, job_id: str, stage_name: str, error: str) -> StandardJob:
        job = self.get_job(job_id)
        if stage_name in job.stages:
            job.stages[stage_name].fail(error)
            self.store.update_job(job)
        return job

    def delete_job(self, job_id: str) -> bool:
        self.get_job(job_id)
        result = self.store.delete_job(job_id)
        logger.info(f"Deleted job {job_id}")
        return result

    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[StandardJob]:
        return self.store.list_jobs(status=status, limit=limit, offset=offset)

    def get_stats(self) -> dict:
        return self.store.get_stats()

    def cleanup_expired(self) -> int:
        count = self.store.cleanup_expired()
        logger.info(f"Cleaned up {count} expired jobs")
        return count