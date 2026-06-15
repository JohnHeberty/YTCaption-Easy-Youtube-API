"""Orchestrate transcription job creation, orphan detection and submission.

This service encapsulates all business logic that was previously embedded in the
``POST /jobs`` route handler of ``jobs_routes.py``, keeping the API layer thin.
"""
from __future__ import annotations

import asyncio
from datetime import datetime as _dt
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from app.domain.interfaces import IJobStore
    from app.domain.models import Job, WhisperEngine
    from app.shared.file_upload_handler import FileUploadHandler


class JobCreationError(Exception):
    """Raised when job creation fails."""


def _default_now() -> "_dt":  # noqa: F821
    from common.datetime_utils import now_brazil

    return now_brazil()


class JobCreationService:
    """Business logic for creating and re-submitting transcription jobs."""

    def __init__(
        self,
        job_store: "IJobStore",
        upload_handler: FileUploadHandler,
        submit_task_fn=None,
        time_fn: Optional[Callable[[], "_dt"]] = None,  # noqa: F821
    ) -> None:
        self.job_store = job_store
        self.upload_handler = upload_handler
        # Callable(job, store) → submits processing (Celery or asyncio fallback).
        self.submit_task_fn = submit_task_fn
        self._time_fn = time_fn or _default_now

    # -- public API ------------------------------------------------------------

    async def create_or_resume_job(
        self,
        file_content: bytes,
        original_filename: Optional[str],
        language_in: str,
        language_out: Optional[str] = None,
        engine: "WhisperEngine" = None,
    ) -> Job:
        """Create a new job or resume an existing one (replay / orphan recovery).

        Returns the ``Job`` instance ready for processing.
        """
        from app.domain.models import Job, WhisperEngine as WE  # noqa: F811 – local to avoid cycles

        if engine is None:
            engine = WE.FASTER_WHISPER

        new_job = Job.create_new(
            original_filename or "unknown",
            operation="transcribe",
            language_in=language_in,
            language_out=language_out,
            engine=engine,
        )

        existing_job = self.job_store.get_job(new_job.id)
        if existing_job is not None:
            return await self._handle_existing_job(
                existing_job, file_content, original_filename
            )

        # Brand new job – persist file and save to store.
        saved_path = await self.upload_handler.save_file(
            file_content, original_filename, new_job.id
        )

        new_job.input_file = str(saved_path.absolute())
        new_job.file_size_input = saved_path.stat().st_size
        self.job_store.save_job(new_job)
        self._submit_task(new_job)
        return new_job

    # -- internal --------------------------------------------------------------

    async def _handle_existing_job(
        self,
        existing: Job,
        file_content: bytes,
        original_filename: Optional[str],
    ) -> Job:
        from app.domain.models import JobStatus  # noqa: F811 – local to avoid cycles

        if existing.status == JobStatus.COMPLETED:
            return existing

        processing_timeout = timedelta(minutes=30)
        job_age = self._time_fn() - existing.created_at

        if existing.status in (JobStatus.QUEUED, JobStatus.PROCESSING):
            if job_age > processing_timeout:
                # Orphan recovery – reset and re-submit.
                return await self._re_submit_job(existing, file_content, original_filename)
            return existing  # Still alive, nothing to do.

        if existing.status == JobStatus.FAILED:
            return await self._re_submit_job(existing, file_content, original_filename)

        return existing

    async def _re_submit_job(
        self,
        job: Job,
        file_content: bytes,
        original_filename: Optional[str],
    ) -> Job:
        from app.domain.models import JobStatus  # noqa: F811 – local to avoid cycles

        saved_path = await self.upload_handler.save_file(
            file_content, original_filename, job.id
        )

        job.input_file = str(saved_path.absolute())
        job.file_size_input = saved_path.stat().st_size
        job.status = JobStatus.QUEUED
        job.error_message = None
        job.progress = 0.0
        self.job_store.update_job(job)
        self._submit_task(job)
        return job

    def _submit_task(self, job: Job) -> None:
        if self.submit_task_fn is not None:
            try:
                self.submit_task_fn(job, self.job_store)
            except Exception as exc:
                from common.log_utils import get_logger  # noqa: F811 – local to avoid cycles

                logger = get_logger(__name__)
                logger.error("Failed to submit task for job %s: %s", job.id, exc)
        else:
            asyncio.create_task(self.job_store.update_job(job))
