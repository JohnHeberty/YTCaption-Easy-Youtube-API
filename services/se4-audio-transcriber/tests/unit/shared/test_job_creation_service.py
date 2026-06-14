"""Unit tests for JobCreationService — job creation, orphan detection, FAILED re-submission."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone as tz
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# --------------------------------------------------------------------------- #
# Fixtures / helpers                                                           #
# --------------------------------------------------------------------------- #

_BRAZIL_TZ = tz(timedelta(hours=-3))


def _fixed_now(offset_minutes: int = 0) -> datetime:
    """Return a deterministic Brazil-time datetime with optional offset."""
    base = datetime(2024, 6, 15, 10, 0, 0, tzinfo=_BRAZIL_TZ)
    return base + timedelta(minutes=offset_minutes)


class _MockJobStore:
    """Minimal in-memory IJobStore mock."""

    def __init__(self):
        self._jobs = {}
        self.save_calls = []
        self.update_calls = []

    def get_job(self, job_id: str):  # noqa: ANN401 – matches interface
        return self._jobs.get(job_id)

    def save_job(self, job):  # noqa: ANN401 – matches interface
        self.save_calls.append(job.id)
        self._jobs[job.id] = job

    async def update_job(self, job):  # noqa: ANN401 – dual-signature for sync + asyncio.create_task calls
        self.update_calls.append(job.id)

    def delete_job(self, job_id: str) -> bool:
        return False


class _MockUploadHandler:
    """Minimal FileUploadHandler mock that writes to a temp directory."""

    def __init__(self, tmp_path):
        self.upload_dir = Path(tmp_path) / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_file(self, file_content: bytes, original_filename: Optional[str], job_id: str) -> Path:
        ext = Path(original_filename).suffix if original_filename else ""
        dest = self.upload_dir / f"{job_id}{ext}"
        dest.write_bytes(file_content)
        return dest


def _make_job(
    job_id: str,
    status="queued",
    created_at_offset_minutes: int = 0,
):
    """Build a bare dict-like object that behaves like a Job for mocking."""
    from common.job_utils.models import JobStatus as JS

    if isinstance(status, str):
        try:
            st = JS(status)
        except ValueError:
            st = status
    else:
        st = status

    job = MagicMock()
    job.id = job_id
    job.status = st
    job.created_at = _fixed_now(created_at_offset_minutes)
    job.input_file = None
    job.file_size_input = 0
    job.error_message = "previous error" if status == "failed" else None
    job.progress = 100.0 if status == "completed" else 50.0

    # Make assignment work (MagicMock allows it by default, but be explicit)
    return job


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #


class TestJobCreationServiceNewJob:
    """Happy-path and basic behaviour for brand-new jobs."""

    @pytest.fixture(autouse=True)
    def _patch_now(self):
        with patch("common.datetime_utils.now_brazil", return_value=_fixed_now()):
            yield

    def test_create_new_job_persists_and_submits(self, tmp_path):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_creation_service import JobCreationService

        store = _MockJobStore()
        upload_handler = _MockUploadHandler(tmp_path)
        submit_fn = MagicMock()

        svc = JobCreationService(store, upload_handler, submit_task_fn=submit_fn)

        result = asyncio.get_event_loop().run_until_complete(
            svc.create_or_resume_job(b"audio-data", "test.mp3", "pt")
        )

        assert store.save_calls  # job was persisted
        saved_id = store.save_calls[0]
        submit_fn.assert_called_once()
        submitted_args = submit_fn.call_args[0]
        assert submitted_args[0].id == result.id
        assert isinstance(submitted_args[1], _MockJobStore)

    def test_create_new_job_sets_file_metadata(self, tmp_path):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_creation_service import JobCreationService

        store = _MockJobStore()
        upload_handler = _MockUploadHandler(tmp_path)

        svc = JobCreationService(store, upload_handler)

        result = asyncio.get_event_loop().run_until_complete(
            svc.create_or_resume_job(b"12345", "input.wav", "en")
        )

        assert result.input_file is not None
        assert Path(result.input_file).exists()
        assert result.file_size_input == 5

    def test_create_new_job_no_submit_fn_uses_asyncio_fallback(self, tmp_path):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_creation_service import JobCreationService

        store = _MockJobStore()
        upload_handler = _MockUploadHandler(tmp_path)

        svc = JobCreationService(store, upload_handler, submit_task_fn=None)

        result = asyncio.get_event_loop().run_until_complete(
            svc.create_or_resume_job(b"data", "file.mp3", "pt")
        )

        assert store.save_calls  # persisted even without Celery


class TestJobCreationServiceExistingCompleted:
    """COMPLETED jobs are returned as-is (no re-processing)."""

    @pytest.fixture(autouse=True)
    def _patch_now(self):
        with patch("common.datetime_utils.now_brazil", return_value=_fixed_now()):
            yield

    def test_completed_job_returned_without_re_submit(self, tmp_path):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_creation_service import JobCreationService

        store = _MockJobStore()
        upload_handler = _MockUploadHandler(tmp_path)
        submit_fn = MagicMock()

        existing = _make_job("existing-1", status="completed")
        # Pre-populate the mock store so get_job returns it.
        store._jobs["existing-1"] = existing
        with patch(
            "common.job_utils.models.generate_job_id", return_value="existing-1"
        ):
            svc = JobCreationService(store, upload_handler, submit_task_fn=submit_fn)

            result = asyncio.get_event_loop().run_until_complete(
                svc.create_or_resume_job(b"data", "test.mp3", "pt")
            )

        assert result.id == "existing-1"
        # Must NOT call save or update for a completed job.
        submit_fn.assert_not_called()


class TestJobCreationServiceOrphanDetection:
    """QUEUED/PROCESSING jobs older than 30 min are treated as orphaned."""

    @pytest.fixture(autouse=True)
    def _patch_now(self):
        with patch("common.datetime_utils.now_brazil", return_value=_fixed_now()):
            yield

    def test_queued_job_within_timeout_returned_as_is(self, tmp_path):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_creation_service import JobCreationService

        store = _MockJobStore()
        upload_handler = _MockUploadHandler(tmp_path)
        submit_fn = MagicMock()

        existing = _make_job("job-1", status="queued", created_at_offset_minutes=-5)
        store._jobs["job-1"] = existing
        with patch(
            "common.job_utils.models.generate_job_id", return_value="job-1"
        ):
            svc = JobCreationService(store, upload_handler, submit_task_fn=submit_fn)

            result = asyncio.get_event_loop().run_until_complete(
                svc.create_or_resume_job(b"data", "test.mp3", "pt")
            )

        assert result.id == "job-1"
        # Should NOT re-submit because job is still within 5 min (under 30).
        submit_fn.assert_not_called()

    def test_queued_job_over_30min_timeout_resubmitted(self, tmp_path):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_creation_service import JobCreationService

        store = _MockJobStore()
        upload_handler = _MockUploadHandler(tmp_path)
        submit_fn = MagicMock()

        existing = _make_job("job-2", status="queued", created_at_offset_minutes=-35)
        store._jobs["job-2"] = existing
        with patch(
            "common.job_utils.models.generate_job_id", return_value="job-2"
        ):
            svc = JobCreationService(store, upload_handler, submit_task_fn=submit_fn)

            result = asyncio.get_event_loop().run_until_complete(
                svc.create_or_resume_job(b"data", "test.mp3", "pt")
            )

        assert result.id == "job-2"
        # Orphan recovery: should re-submit.
        submit_fn.assert_called_once()


class TestJobCreationServiceFailedResubmission:
    """FAILED jobs are reset and re-submitted via callable DI."""

    @pytest.fixture(autouse=True)
    def _patch_now(self):
        with patch("common.datetime_utils.now_brazil", return_value=_fixed_now()):
            yield

    def test_failed_job_resubmitted_via_callable_di(self, tmp_path):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_creation_service import JobCreationService

        store = _MockJobStore()
        upload_handler = _MockUploadHandler(tmp_path)
        submit_fn = MagicMock()

        existing = _make_job("job-3", status="failed")
        store._jobs["job-3"] = existing
        with patch(
            "common.job_utils.models.generate_job_id", return_value="job-3"
        ):
            svc = JobCreationService(store, upload_handler, submit_task_fn=submit_fn)

            result = asyncio.get_event_loop().run_until_complete(
                svc.create_or_resume_job(b"data", "test.mp3", "pt")
            )

        assert result.id == "job-3"
        # Re-submission should happen.
        submit_fn.assert_called_once()
        submitted_args = submit_fn.call_args[0]
        job_arg, store_arg = submitted_args
        assert job_arg.id == "job-3"


class TestJobCreationServiceSubmitTaskErrorHandling:
    """_submit_task swallows exceptions and logs them."""

    @pytest.fixture(autouse=True)
    def _patch_now(self):
        with patch("common.datetime_utils.now_brazil", return_value=_fixed_now()):
            yield

    def test_submit_fn_exception_does_not_crash_creation(self, tmp_path, caplog):  # noqa: ARG002 – fixture side-effects
        import logging as log_mod

        from app.shared.job_creation_service import JobCreationService

        store = _MockJobStore()
        upload_handler = _MockUploadHandler(tmp_path)

        def bad_submit(job, job_store):
            raise RuntimeError("broker unavailable")

        svc = JobCreationService(store, upload_handler, submit_task_fn=bad_submit)

        with caplog.at_level(log_mod.ERROR):
            result = asyncio.get_event_loop().run_until_complete(
                svc.create_or_resume_job(b"data", "test.mp3", "pt")
            )

        assert store.save_calls  # job still persisted despite broker error.
        assert "Failed to submit task" in caplog.text


class TestJobCreationServiceDefaultEngine:
    """When engine is None, default should be FASTER_WHISPER."""

    @pytest.fixture(autouse=True)
    def _patch_now(self):
        with patch("common.datetime_utils.now_brazil", return_value=_fixed_now()):
            yield

    def test_default_engine_is_faster_whisper(self, tmp_path):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_creation_service import JobCreationService

        store = _MockJobStore()
        upload_handler = _MockUploadHandler(tmp_path)

        svc = JobCreationService(store, upload_handler)

        result = asyncio.get_event_loop().run_until_complete(
            svc.create_or_resume_job(b"data", "test.mp3", "pt")
        )

        assert result.engine.value == "faster-whisper", (
            f"Expected faster-whisper engine but got {result.engine}"
        )



class TestJobCreationServiceUnknownExistingStatus:
    """Jobs in an unexpected status are returned as-is."""

    @pytest.fixture(autouse=True)
    def _patch_now(self):
        with patch("common.datetime_utils.now_brazil", return_value=_fixed_now()):
            yield

    def test_unknown_status_returned_without_resubmit(self, tmp_path):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_creation_service import JobCreationService

        store = _MockJobStore()
        upload_handler = _MockUploadHandler(tmp_path)
        submit_fn = MagicMock()

        existing = _make_job("job-4", status="cancelled")
        store._jobs["job-4"] = existing
        with patch(
            "common.job_utils.models.generate_job_id", return_value="job-4"
        ):
            svc = JobCreationService(store, upload_handler, submit_task_fn=submit_fn)

            result = asyncio.get_event_loop().run_until_complete(
                svc.create_or_resume_job(b"data", "test.mp3", "pt")
            )

        assert result.id == "job-4"
        # Should NOT re-submit for cancelled/unknown status.
        submit_fn.assert_not_called()


class TestJobCreationServiceProcessingOrphan:
    """PROCESSING jobs over 30 min are also orphan-recovered."""

    @pytest.fixture(autouse=True)
    def _patch_now(self):
        with patch("common.datetime_utils.now_brazil", return_value=_fixed_now()):
            yield

    def test_processing_job_over_timeout_resubmitted(self, tmp_path):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_creation_service import JobCreationService

        store = _MockJobStore()
        upload_handler = _MockUploadHandler(tmp_path)
        submit_fn = MagicMock()

        existing = _make_job("job-5", status="processing", created_at_offset_minutes=-40)
        store._jobs["job-5"] = existing
        with patch(
            "common.job_utils.models.generate_job_id", return_value="job-5"
        ):
            svc = JobCreationService(store, upload_handler, submit_task_fn=submit_fn)

            result = asyncio.get_event_loop().run_until_complete(
                svc.create_or_resume_job(b"data", "test.mp3", "pt")
            )

        assert result.id == "job-5"
        # Orphan recovery for PROCESSING.
        submit_fn.assert_called_once()


class TestJobCreationServiceProcessingWithinTimeout:
    """PROCESSING jobs within 30 min are left alone."""

    @pytest.fixture(autouse=True)
    def _patch_now(self):
        with patch("common.datetime_utils.now_brazil", return_value=_fixed_now()):
            yield

    def test_processing_job_within_timeout_returned_as_is(self, tmp_path):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_creation_service import JobCreationService

        store = _MockJobStore()
        upload_handler = _MockUploadHandler(tmp_path)
        submit_fn = MagicMock()

        existing = _make_job("job-6", status="processing", created_at_offset_minutes=-10)
        store._jobs["job-6"] = existing
        with patch(
            "common.job_utils.models.generate_job_id", return_value="job-6"
        ):
            svc = JobCreationService(store, upload_handler, submit_task_fn=submit_fn)

            result = asyncio.get_event_loop().run_until_complete(
                svc.create_or_resume_job(b"data", "test.mp3", "pt")
            )

        assert result.id == "job-6"
        # Still alive — no re-submission.
        submit_fn.assert_not_called()


class TestJobCreationServiceResubmitClearsError:
    """Re-submitting a FAILED job clears error_message and resets progress."""

    @pytest.fixture(autouse=True)
    def _patch_now(self):
        with patch("common.datetime_utils.now_brazil", return_value=_fixed_now()):
            yield

    def test_resubmit_clears_error_and_progress(self, tmp_path):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_creation_service import JobCreationService

        store = _MockJobStore()
        upload_handler = _MockUploadHandler(tmp_path)
        submit_fn = MagicMock()

        existing = _make_job("job-7", status="failed")
        with patch(
            "common.job_utils.models.generate_job_id", return_value="job-7"
        ):
            svc = JobCreationService(store, upload_handler, submit_task_fn=submit_fn)

            result = asyncio.get_event_loop().run_until_complete(
                svc.create_or_resume_job(b"data", "test.mp3", "pt")
            )

        assert result.id == "job-7"
        # _re_submit_job sets error_message=None and progress=0.0 on the job object.
        submitted_args = submit_fn.call_args[0]
        resubmitted_job = submitted_args[0]
        assert resubmitted_job.error_message is None, (
            f"Expected cleared error but got {resubmitted_job.error_message}"
        )
