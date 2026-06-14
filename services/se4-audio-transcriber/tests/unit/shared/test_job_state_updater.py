"""Unit tests for JobStateUpdater — shared job state persistence helper."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone as tz
from typing import Any, Optional
from unittest.mock import patch

import pytest


class _MockJob:  # noqa: SIM119 – lightweight data carrier for tests
    """Minimal stand-in for the domain Job model."""

    def __init__(self, job_id="job-001", status="queued"):
        self.id = job_id
        from app.shared.job_states import JobStatus as _JS  # noqa: N812 – local alias

        if isinstance(status, str):
            try:
                self.status = _JS(status)
            except ValueError:
                self.status = status
        else:
            self.status = status

        self.progress = 0.0
        self.started_at = None
        self.completed_at = None
        self.processing_time = None
        self.error = None
        self.output_path = None
        self.result_text = ""
        self.segments = None
        self.file_size_output = 0
        self.language_detected = None
        self.updated_at = None


class _MockStore:
    """Minimal IJobStore mock backed by an in-memory dict."""

    def __init__(self):
        self._jobs = {}
        self.update_error = False

    def get_job(self, job_id):  # noqa: ANN401 – matches interface
        return self._jobs.get(job_id)

    def update_job(self, job):  # noqa: ANN401 – matches interface
        if self.update_error:
            raise RuntimeError("store explosion")
        self._jobs[job.id] = job


def _status_value(job):
    """Return the string value of a JobStatus enum or raw status."""
    return job.status.value if hasattr(job.status, "value") else str(job.status)


class TestMarkProcessing:

    def test_queued_to_processing_sets_status_and_started_at(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        store = _MockStore()
        job = _MockJob(job_id="job-1", status="queued")
        store._jobs["job-1"] = job

        updater = JobStateUpdater(store)
        updater.mark_processing(job)

        assert _status_value(job) == "processing"
        assert job.started_at is not None

    def test_invalid_transition_logged_and_ignored(self, caplog):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        store = _MockStore()
        job = _MockJob(job_id="job-2", status="completed")
        store._jobs["job-2"] = job

        updater = JobStateUpdater(store)
        with caplog.at_level(logging.WARNING):
            updater.mark_processing(job)

        assert "Skipping mark_processing" in caplog.text


class TestSafeUpdate:

    def test_store_error_captured_not_propagated(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        store = _MockStore()
        store.update_error = True
        job = _MockJob(job_id="job-3", status="queued")
        store._jobs["job-3"] = job

        updater = JobStateUpdater(store)
        # Should NOT raise even though update_job raises RuntimeError.
        updater.safe_update(job)


class TestSetProgress:

    def test_sets_progress_and_persists(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        store = _MockStore()
        job = _MockJob(job_id="job-4", status="processing")
        store._jobs["job-4"] = job

        updater = JobStateUpdater(store)
        updater.set_progress(50.0, "job-4")

        assert job.progress == 50.0
        persisted = store.get_job("job-4")
        assert persisted is not None
        assert persisted.updated_at is not None


class TestMarkCompleted:

    def test_job_object_applies_completed_state(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        store = _MockStore()
        now_brazil_tz = tz(timedelta(hours=-3))
        started = datetime(2024, 1, 1, 12, 0, 0, tzinfo=now_brazil_tz)
        job = _MockJob(job_id="job-5", status="processing")
        job.started_at = started
        store._jobs["job-5"] = job

        updater = JobStateUpdater(store)
        with patch("app.shared.job_state_updater._now_brazil"):
            frozen_time = datetime(2024, 1, 1, 12, 5, 0, tzinfo=now_brazil_tz)
            import app.shared.job_state_updater as jsu_mod

            original = jsu_mod._now_brazil
            jsu_mod._now_brazil = lambda: frozen_time  # noqa: ARG005 – test fixture
            try:
                updater.mark_completed(job)
            finally:
                jsu_mod._now_brazil = original

        assert _status_value(job) == "completed"
        assert job.completed_at is not None
        assert job.processing_time == pytest.approx(300.0, abs=2.0), (
            "processing_time should be ~5 min = 300s"
        )

    def test_job_id_string_fetches_via_store(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        store = _MockStore()
        job = _MockJob(job_id="job-6", status="processing")
        store._jobs["job-6"] = job

        updater = JobStateUpdater(store)
        with patch("app.shared.job_state_updater._now_brazil"):
            frozen_time = datetime(2024, 1, 1, 12, 5, 0, tzinfo=tz(timedelta(hours=-3)))
            import app.shared.job_state_updater as jsu_mod

            original = jsu_mod._now_brazil
            jsu_mod._now_brazil = lambda: frozen_time  # noqa: ARG005 – test fixture
            try:
                updater.mark_completed("job-6")
            finally:
                jsu_mod._now_brazil = original

        assert _status_value(job) == "completed"


class TestMarkFailed:

    def test_job_object_applies_failed_state(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        store = _MockStore()
        now_brazil_tz = tz(timedelta(hours=-3))
        started = datetime(2024, 1, 1, 12, 0, 0, tzinfo=now_brazil_tz)
        job = _MockJob(job_id="job-7", status="processing")
        job.started_at = started
        store._jobs["job-7"] = job

        updater = JobStateUpdater(store)
        with patch("app.shared.job_state_updater._now_brazil"):
            frozen_time = datetime(2024, 1, 1, 12, 5, 0, tzinfo=now_brazil_tz)
            import app.shared.job_state_updater as jsu_mod

            original = jsu_mod._now_brazil
            jsu_mod._now_brazil = lambda: frozen_time  # noqa: ARG005 – test fixture
            try:
                updater.mark_failed(job, "something went wrong")
            finally:
                jsu_mod._now_brazil = original

        assert _status_value(job) == "failed"
        assert job.completed_at is not None
        assert job.error == "something went wrong"

    def test_error_truncated_to_1024_chars(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        store = _MockStore()
        job = _MockJob(job_id="job-8", status="processing")
        store._jobs["job-8"] = job

        updater = JobStateUpdater(store)
        long_error = "X" * 2048
        updater.mark_failed(job, long_error)

        assert _status_value(job) == "failed"
        assert len(job.error or "") <= 1024

    def test_job_id_string_fetches_via_store(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        store = _MockStore()
        job = _MockJob(job_id="job-9", status="processing")
        store._jobs["job-9"] = job

        updater = JobStateUpdater(store)
        with patch("app.shared.job_state_updater._now_brazil"):
            frozen_time = datetime(2024, 1, 1, 12, 5, 0, tzinfo=tz(timedelta(hours=-3)))
            import app.shared.job_state_updater as jsu_mod

            original = jsu_mod._now_brazil
            jsu_mod._now_brazil = lambda: frozen_time  # noqa: ARG005 – test fixture
            try:
                updater.mark_failed("job-9", "store-fetched failure")
            finally:
                jsu_mod._now_brazil = original

        assert _status_value(job) == "failed"


class TestIProgressTrackerDelegation:

    def test_update_progress_delegates_to_set_progress(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        store = _MockStore()
        job = _MockJob(job_id="job-10", status="processing")
        store._jobs["job-10"] = job

        updater = JobStateUpdater(store)
        with patch.object(updater, "set_progress", wraps=updater.set_progress) as spy:
            updater.update_progress("job-10", 75.0, "halfway there")

        assert spy.called
        args, kwargs = spy.call_args
        # set_progress(progress, job_id=id) — positional first arg is progress
        assert (args[0] == 75.0 or kwargs.get("progress") == 75.0), f"Expected progress=75, got call {spy.call_args}"

    def test_mark_started_fetches_and_marks_processing(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        store = _MockStore()
        job = _MockJob(job_id="job-11", status="queued")
        store._jobs["job-11"] = job

        updater = JobStateUpdater(store)
        with patch("app.shared.job_state_updater._now_brazil"):
            frozen_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=tz(timedelta(hours=-3)))
            import app.shared.job_state_updater as jsu_mod

            original = jsu_mod._now_brazil
            jsu_mod._now_brazil = lambda: frozen_time  # noqa: ARG005 – test fixture
            try:
                updater.mark_started("job-11")
            finally:
                jsu_mod._now_brazil = original

        assert _status_value(job) == "processing"


class TestDefensiveNoOpWhenStoreNone:

    def test_mark_processing_no_crash(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        updater = JobStateUpdater(None)
        job = _MockJob(job_id="job-12", status="queued")
        updater.mark_processing(job)

    def test_safe_update_no_crash(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        updater = JobStateUpdater(None)
        job = _MockJob(job_id="job-13", status="queued")
        updater.safe_update(job)

    def test_set_progress_no_crash(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        updater = JobStateUpdater(None)
        updater.set_progress(50.0, "job-14")

    def test_mark_completed_job_object_no_crash(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        updater = JobStateUpdater(None)
        job = _MockJob(job_id="job-15", status="processing")
        updater.mark_completed(job)

    def test_mark_completed_job_id_no_crash(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        updater = JobStateUpdater(None)
        updater.mark_completed("job-16")

    def test_mark_failed_job_object_no_crash(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        updater = JobStateUpdater(None)
        job = _MockJob(job_id="job-17", status="processing")
        updater.mark_failed(job, "error msg")

    def test_mark_failed_job_id_no_crash(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        updater = JobStateUpdater(None)
        updater.mark_failed("job-18", "error msg")

    def test_update_progress_no_crash(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        updater = JobStateUpdater(None)
        updater.update_progress("job-19", 50.0, "msg")

    def test_mark_started_no_crash(self):  # noqa: ARG002 – fixture side-effects
        from app.shared.job_state_updater import JobStateUpdater

        updater = JobStateUpdater(None)
        updater.mark_started("job-20")
