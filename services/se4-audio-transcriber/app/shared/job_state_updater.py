"""Centralised job state persistence helper.

Wraps every ``IJobStore.update_job()`` call with error suppression, timestamp
injection and processing-time bookkeeping so that a transient store failure never
brakes the main transcription flow.

Also implements IProgressTracker from the domain layer, unifying progress/state
tracking into a single class (replaces RedisProgressTracker).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone as tz  # noqa: F401 – used by callers
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..domain.models import Job

# IProgressTracker is needed at runtime for class inheritance.
from ..domain.interfaces import IJobStore  # noqa: F401 – re-exported by interfaces.__all__
from ..domain.interfaces import IProgressTracker


logger = logging.getLogger(__name__)


def _now_brazil() -> datetime:
    """Current time in America/Sao_Paulo (UTC-3)."""
    return datetime.now(tz(timedelta(hours=-3)))  # type: ignore[arg-type]


class JobStateUpdater(IProgressTracker):
    """Thin wrapper around ``IJobStore`` that keeps job persistence safe.

    Implements IProgressTracker so callers can use either the job-based API
    (mark_completed(job, ...), mark_failed(job, msg)) or the interface's
    job_id-based API (mark_started(id), update_progress(id, pct)).
    """

    def __init__(self, job_store: Optional[IJobStore] = None) -> None:
        self.job_store = job_store

    # -- IProgressTracker interface (job_id-based API) -------------------------

    def update_progress(self, job_id: str, progress: float, message: str = "") -> None:  # type: ignore[override]
        """IProgressTracker.update_progress — delegates to set_progress."""
        self.set_progress(progress, job_id=job_id)

    def mark_started(self, job_id: str) -> None:
        """IProgressTracker.mark_started — fetches the job and marks PROCESSING."""
        if not self.job_store:
            return
        try:
            job = self.job_store.get_job(job_id)  # type: ignore[attr-defined]
            if job is not None:
                self.mark_processing(job)
        except Exception as exc:
            logger.error("Failed to mark_started for %s: %s", job_id, exc)

    # -- low-level primitive ---------------------------------------------------

    @staticmethod
    def _safe_update(job_store: IJobStore, job: "Job") -> None:  # type: ignore[type-arg]
        """Persist *job* without propagating store errors."""
        if not job_store:
            return
        try:
            if hasattr(job, "updated_at"):
                job.updated_at = _now_brazil()  # type: ignore[attr-defined]
            job_store.update_job(job)
        except Exception as exc:
            logger.error("Failed to persist job %s: %s", getattr(job, "id", "?"), exc)

    def safe_update(self, job: "Job") -> None:
        """Persist *job* using the injected store."""
        self._safe_update(self.job_store, job)  # type: ignore[arg-type]

    # -- high-level helpers ----------------------------------------------------

    def mark_processing(self, job: "Job", started_at: Optional[datetime] = None) -> None:
        """Mark a job as ``PROCESSING``."""
        from .job_states import JobStateMachine, JobStatus  # noqa: F811 – local to avoid cycles

        sm = JobStateMachine(job.status.value if hasattr(job.status, "value") else str(job.status))
        if not sm.can_transition_to(JobStatus.PROCESSING):
            logger.warning(
                "Skipping mark_processing for job %s (current=%s)",
                getattr(job, "id", "?"),
                sm.current.value,
            )
            return

        from ..domain.models import JobStatus as DomainJobStatus  # noqa: F811 – local to avoid cycles
        if hasattr(job.status, "value"):
            job.status = DomainJobStatus.PROCESSING  # type: ignore[attr-defined]
        else:
            job.status = JobStatus.PROCESSING.value  # type: ignore[attr-defined]

        sm.transition_to(JobStatus.PROCESSING)

        if not getattr(job, "started_at", None):
            job.started_at = started_at or _now_brazil()  # type: ignore[attr-defined]
        self.safe_update(job)

    def set_progress(self, progress: float, job_id: Optional[str] = None) -> None:
        """Update progress for an already-known *job_id*."""
        if not self.job_store or not job_id:
            return
        try:
            job = self.job_store.get_job(job_id)  # type: ignore[attr-defined]
            if job is not None:
                job.progress = progress  # type: ignore[attr-defined]
                self.safe_update(job)
        except Exception as exc:
            logger.error("Failed to set progress for %s: %s", job_id, exc)

    def mark_completed(
        self,
        first_arg: Any,
        *,
        output_file: Optional[str] = None,
        text: str = "",
        segments: Any = None,
        file_size_output: int = 0,
        language_detected: Optional[str] = None,
    ) -> None:
        """Finalise a job as ``COMPLETED``.

        Accepts either a Job object (existing API) or a job_id string
        (IProgressTracker interface). When called with a job_id the optional
        keyword arguments are ignored and the store is queried for metadata.
        """
        if isinstance(first_arg, str):
            # IProgressTracker.mark_completed(job_id, result) path
            if self.job_store:
                try:
                    job = self.job_store.get_job(first_arg)  # type: ignore[attr-defined]
                    if job is not None:
                        self._apply_completed(
                            job, output_file=output_file, text=text, segments=segments, file_size_output=file_size_output, language_detected=language_detected
                        )
                except Exception as exc:
                    logger.error("Failed to mark_completed for %s: %s", first_arg, exc)
            return

        self._apply_completed(first_arg, output_file=output_file, text=text, segments=segments, file_size_output=file_size_output, language_detected=language_detected)

    def _apply_completed(
        self, job: "Job", *, output_file: Optional[str] = None, text: str = "", segments: Any = None, file_size_output: int = 0, language_detected: Optional[str] = None
    ) -> None:
        """Apply COMPLETED state to a Job object."""
        from .job_states import JobStateMachine, JobStatus

        sm = JobStateMachine(job.status.value if hasattr(job.status, "value") else str(job.status))
        if not sm.can_transition_to(JobStatus.COMPLETED):
            logger.warning(
                "Skipping mark_completed for job %s (current=%s)",
                getattr(job, "id", "?"),
                sm.current.value,
            )

        from ..domain.models import JobStatus as DomainJobStatus  # noqa: F811 – local to avoid cycles
        if hasattr(job.status, "value"):
            job.status = DomainJobStatus.COMPLETED  # type: ignore[attr-defined]
        else:
            job.status = JobStatus.COMPLETED.value  # type: ignore[attr-defined]

        sm.transition_to(JobStatus.COMPLETED)

        now = _now_brazil()
        if hasattr(job, "completed_at"):
            job.completed_at = now  # type: ignore[attr-defined]
        if hasattr(job, "progress"):
            job.progress = 100.0  # type: ignore[attr-defined]
        if output_file and hasattr(job, "output_path"):
            job.output_path = output_file  # type: ignore[attr-defined]
        if text and hasattr(job, "result_text"):
            job.result_text = text  # type: ignore[attr-defined]
        if segments is not None and hasattr(job, "segments"):
            job.segments = segments  # type: ignore[attr-defined]
        if file_size_output > 0 and hasattr(job, "file_size_output"):
            job.file_size_output = file_size_output  # type: ignore[attr-defined]
        if language_detected is not None and hasattr(job, "language_detected"):
            job.language_detected = language_detected  # type: ignore[attr-defined]

        started_at_val = getattr(job, "started_at", None) or now
        finished_at_val = _now_brazil()
        processing_time_seconds = (finished_at_val - started_at_val).total_seconds() if hasattr(started_at_val, "__sub__") else 0.0
        if hasattr(job, "processing_time"):
            job.processing_time = round(processing_time_seconds, 2)  # type: ignore[attr-defined]

        self.safe_update(job)

    def mark_failed(self, first_arg: Any, error_message_or_result: str = "") -> None:
        """Finalise a job as ``FAILED``.

        Accepts either (job, message) — existing API — or (job_id, result)
        when called via IProgressTracker interface.
        """
        if isinstance(first_arg, str):
            # IProgressTracker.mark_failed(job_id, error) path
            job_id = first_arg
            err = str(error_message_or_result) if not isinstance(error_message_or_result, str) else error_message_or_result
            if self.job_store:
                try:
                    job = self.job_store.get_job(job_id)  # type: ignore[attr-defined]
                    if job is not None:
                        self._apply_failed(job, err or f"Job {job_id} failed")
                except Exception as exc:
                    logger.error("Failed to mark_failed for %s: %s", job_id, exc)
            return

        # Existing API: (job, error_message)
        self._apply_failed(first_arg, str(error_message_or_result))

    def _apply_failed(self, job: "Job", error_message: str) -> None:
        """Apply FAILED state to a Job object."""
        from .job_states import JobStateMachine, JobStatus

        sm = JobStateMachine(job.status.value if hasattr(job.status, "value") else str(job.status))
        if not sm.can_transition_to(JobStatus.FAILED):
            logger.warning(
                "Skipping mark_failed for job %s (current=%s)",
                getattr(job, "id", "?"),
                sm.current.value,
            )

        from ..domain.models import JobStatus as DomainJobStatus  # noqa: F811 – local to avoid cycles
        if hasattr(job.status, "value"):
            job.status = DomainJobStatus.FAILED  # type: ignore[attr-defined]
        else:
            job.status = JobStatus.FAILED.value  # type: ignore[attr-defined]

        sm.transition_to(JobStatus.FAILED)

        now = _now_brazil()
        if hasattr(job, "completed_at"):
            job.completed_at = now  # type: ignore[attr-defined]
        if error_message and hasattr(job, "error"):
            job.error = error_message[:1024]  # cap length to avoid huge payloads  # type: ignore[attr-defined]

        started_at_val = getattr(job, "started_at", None) or now
        finished_at_val = _now_brazil()
        processing_time_seconds = (finished_at_val - started_at_val).total_seconds() if hasattr(started_at_val, "__sub__") else 0.0
        if hasattr(job, "processing_time"):
            job.processing_time = round(processing_time_seconds, 2)  # type: ignore[attr-defined]

        self.safe_update(job)


# Backward-compatible aliases for legacy code that imports these names directly.
mark_completed_impl = JobStateUpdater._apply_completed.__func__ if hasattr(JobStateUpdater._apply_completed, "__func__") else None  # noqa: F841 – deprecated alias
mark_failed_impl = JobStateUpdater._apply_failed.__func__ if hasattr(JobStateUpdater._apply_failed, "__func__") else None  # noqa: F841 – deprecated alias
