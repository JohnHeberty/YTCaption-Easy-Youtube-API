"""JobStateUpdater ↔ Redis persistence integration tests via fakeredis."""
from pathlib import Path

import pytest


class TestJobStateUpdaterRedisPersistence:
    """Verify JobStateUpdater correctly persists state through IJobStore (fakeredis)."""

    def test_mark_processing_persists_to_redis(self, sample_job, mock_job_store_fakeredis):
        from app.shared.job_state_updater import JobStateUpdater

        store = mock_job_store_fakeredis
        store.save_job(sample_job)

        updater = JobStateUpdater(job_store=store)
        job = store.get_job(sample_job.id)
        updater.mark_processing(job)

        persisted = store.get_job(sample_job.id)
        assert persisted is not None
        assert str(persisted.status) in ("processing", "PROCESSING") or "process" in str(persisted.status).lower()
        assert hasattr(persisted, 'started_at') and persisted.started_at is not None

    def test_set_progress_persists_to_redis(self, sample_job, mock_job_store_fakeredis):
        from app.shared.job_state_updater import JobStateUpdater

        store = mock_job_store_fakeredis
        store.save_job(sample_job)

        updater = JobStateUpdater(job_store=store)
        job = store.get_job(sample_job.id)
        updater.mark_processing(job)

        updater.set_progress(50.0, sample_job.id)
        persisted = store.get_job(sample_job.id)
        assert persisted is not None
        assert persisted.progress == 50.0

    def test_mark_completed_persists_to_redis(self, sample_job, mock_job_store_fakeredis):
        from app.shared.job_state_updater import JobStateUpdater

        store = mock_job_store_fakeredis
        store.save_job(sample_job)

        updater = JobStateUpdater(job_store=store)
        job = store.get_job(sample_job.id)
        updater.mark_processing(job)

        output_path = "/tmp/output/test.srt"
        result_text = "Final transcribed text content here."
        segments_data = [{"start": 0, "end": 5, "text": "Test segment"}]
        file_size_output = 1234
        language_detected = "pt-BR"

        updater.mark_completed(
            job,
            output_file=output_path,
            text=result_text,
            segments=segments_data,
            file_size_output=file_size_output,
            language_detected=language_detected,
        )

        persisted = store.get_job(sample_job.id)
        assert persisted is not None
        assert "complete" in str(persisted.status).lower() or "completed" == str(persisted.status).lower()
        if hasattr(persisted, 'progress'):
            assert persisted.progress == 100.0

    def test_mark_completed_via_job_id_string(self, sample_job, mock_job_store_fakeredis):
        """Test IProgressTracker interface: mark_completed(job_id) path."""
        from app.shared.job_state_updater import JobStateUpdater

        store = mock_job_store_fakeredis
        store.save_job(sample_job)

        updater = JobStateUpdater(job_store=store)
        job = store.get_job(sample_job.id)
        updater.mark_processing(job)

        # Call via job_id string (IProgressTracker interface)
        updater.mark_completed(sample_job.id, output_file="/tmp/out.srt", text="done")

        persisted = store.get_job(sample_job.id)
        assert persisted is not None

    def test_mark_failed_persists_to_redis(self, sample_job, mock_job_store_fakeredis):
        from app.shared.job_state_updater import JobStateUpdater

        store = mock_job_store_fakeredis
        store.save_job(sample_job)

        updater = JobStateUpdater(job_store=store)
        job = store.get_job(sample_job.id)
        updater.mark_processing(job)

        error_msg = "Simulated engine failure during transcription"
        updater.mark_failed(job, error_message_or_result=error_msg)

        persisted = store.get_job(sample_job.id)
        assert persisted is not None
        assert "fail" in str(persisted.status).lower() or "failed" == str(persisted.status).lower()

    def test_mark_failed_via_job_id_string(self, sample_job, mock_job_store_fakeredis):
        """Test IProgressTracker interface: mark_failed(job_id) path."""
        from app.shared.job_state_updater import JobStateUpdater

        store = mock_job_store_fakeredis
        store.save_job(sample_job)

        updater = JobStateUpdater(job_store=store)
        job = store.get_job(sample_job.id)
        updater.mark_processing(job)

        # Call via job_id string (IProgressTracker interface)
        updater.mark_failed(sample_job.id, error_message_or_result="engine timeout")

        persisted = store.get_job(sample_job.id)
        assert persisted is not None

    def test_mark_started_fetches_and_processes(self, sample_job, mock_job_store_fakeredis):
        """Test IProgressTracker interface: mark_started(job_id)."""
        from app.shared.job_state_updater import JobStateUpdater

        store = mock_job_store_fakeredis
        store.save_job(sample_job)

        updater = JobStateUpdater(job_store=store)
        updater.mark_started(sample_job.id)

        persisted = store.get_job(sample_job.id)
        assert persisted is not None


class TestJobStateUpdaterNoStore:
    """Verify graceful degradation when job_store is None."""

    def test_mark_processing_noop_without_store(self, sample_job):
        from app.shared.job_state_updater import JobStateUpdater

        updater = JobStateUpdater(job_store=None)
        # Should not raise even without a store
        try:
            updater.mark_processing(sample_job)
        except Exception as exc:
            pytest.fail(f"mark_processing should handle None store gracefully, got: {exc}")

    def test_set_progress_noop_without_store(self):
        from app.shared.job_state_updater import JobStateUpdater

        updater = JobStateUpdater(job_store=None)
        updater.set_progress(50.0, "nonexistent_job")  # Should be a no-op


class TestJobStateUpdaterProgressTracking:
    """Verify progress values are monotonic and within expected range."""

    def test_incremental_progress_updates(self, sample_job, mock_job_store_fakeredis):
        from app.shared.job_state_updater import JobStateUpdater

        store = mock_job_store_fakeredis
        store.save_job(sample_job)

        updater = JobStateUpdater(job_store=store)
        job = store.get_job(sample_job.id)
        updater.mark_processing(job)

        for pct in [10.0, 30.0, 55.0, 78.0]:
            updater.set_progress(pct, sample_job.id)
            persisted = store.get_job(sample_job.id)
            assert persisted is not None
            assert persisted.progress == pct

    def test_mark_completed_sets_100_percent(self, sample_job, mock_job_store_fakeredis):
        from app.shared.job_state_updater import JobStateUpdater

        store = mock_job_store_fakeredis
        store.save_job(sample_job)

        updater = JobStateUpdater(job_store=store)
        job = store.get_job(sample_job.id)
        updater.mark_processing(job)

        updater.set_progress(40.0, sample_job.id)
        updater.mark_completed(job, output_file="/tmp/final.srt", text="completed")

        persisted = store.get_job(sample_job.id)
        assert persisted is not None
        if hasattr(persisted, 'progress'):
            assert persisted.progress == 100.0


class TestJobStateUpdaterSafeUpdate:
    """Verify _safe_update error suppression."""

    def test_safe_update_catches_store_error(self):
        from app.shared.job_state_updater import JobStateUpdater

        class BrokenStore:
            def update_job(self, job):
                raise RuntimeError("Redis connection lost")

        updater = JobStateUpdater(job_store=BrokenStore())
        # Should not propagate the exception
        try:
            updater.safe_update(type('Job', (), {'id': 'test_123'})())  # noqa: F841
        except Exception as exc:
            pytest.fail(f"safe_update should suppress store errors, got: {exc}")
