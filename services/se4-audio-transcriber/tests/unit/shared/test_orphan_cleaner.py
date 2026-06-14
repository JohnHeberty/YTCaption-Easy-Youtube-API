"""Tests for OrphanJobCleaner - orphan detection and cleanup logic."""
from datetime import timedelta, timezone

try:
    from zoneinfo import ZoneInfo as _zi
except ImportError:
    class ZI:  # noqa: N801
        def __init__(self, *a): pass
    _zi = ZI

BRAZIL_TZ = _zi("America/Sao_Paulo")


def make_fixed_dt(year=2025, month=1, day=15, hour=12, minute=0, second=0):
    from datetime import datetime as dt_cls
    return dt_cls(year, month, day, hour, minute, second, tzinfo=BRAZIL_TZ)


from unittest.mock import patch

import pytest

with patch("common.datetime_utils.now_brazil", return_value=make_fixed_dt()):
    from app.shared.orphan_cleaner import OrphanJobCleaner, DeadLetterQueueManager
    from common.job_utils.models import JobStatus


class MockJobStore:
    """Minimal in-memory IJobStore for orphan tests."""

    def __init__(self):
        self._jobs = {}

    def get_job(self, job_id):
        return self._jobs.get(job_id)

    def save_job(self, job):
        self._jobs[job.id] = job

    def update_job(self, job):
        self._jobs[job.id] = job

    def list_jobs(self, status=None):
        jobs = list(self._jobs.values())
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        return sorted(jobs, key=lambda j: j.created_at)


def _make_job(
    store,
    job_id="job_1",
    status=JobStatus.QUEUED,
    started_at=None,
    created_at=None,
    retry_count=0,
):
    from app.domain.models import AudioTranscriptionJob

    fixed = make_fixed_dt() if created_at is None else created_at
    job = AudioTranscriptionJob(
        id=job_id,
        status=status,
        started_at=started_at,
        created_at=fixed,
        retry_count=retry_count,
    )
    store.save_job(job)
    return job


@pytest.fixture()
def fixed_now():
    """Return a deterministic Brazil-time datetime."""
    return make_fixed_dt(2025, 1, 15, 12, 0, 0)


@pytest.fixture()
def now_patch(fixed_now):
    with patch("common.datetime_utils.now_brazil", return_value=fixed_now):
        yield fixed_now


# -- _is_orphan_processing ---------------------------------------------------

class TestIsOrphanProcessing:
    def test_no_started_at_is_orphan(self, store, now_patch):
        job = _make_job(store, status=JobStatus.PROCESSING, started_at=None)
        cleaner = OrphanJobCleaner(store)
        assert cleaner._is_orphan_processing(job) is True

    def test_within_timeout_not_orphan(self, store, now_patch):
        fixed = make_fixed_dt(2025, 1, 15, 11, 56, 0)
        job = _make_job(store, status=JobStatus.PROCESSING, started_at=fixed)
        cleaner = OrphanJobCleaner(store, processing_timeout_minutes=10)
        assert cleaner._is_orphan_processing(job) is False

    def test_exceeds_timeout_is_orphan(self, store, now_patch):
        fixed = make_fixed_dt(2025, 1, 15, 11, 49, 0)
        job = _make_job(store, status=JobStatus.PROCESSING, started_at=fixed)
        cleaner = OrphanJobCleaner(store, processing_timeout_minutes=10)
        assert cleaner._is_orphan_processing(job) is True

    def test_exactly_at_boundary_not_orphan(self, store):
        fixed_now_val = make_fixed_dt(2025, 1, 15, 12, 0, 0)
        started = make_fixed_dt(2025, 1, 15, 11, 50, 0)
        with patch("common.datetime_utils.now_brazil", return_value=fixed_now_val):
            job = _make_job(store, status=JobStatus.PROCESSING, started_at=started)
            cleaner = OrphanJobCleaner(store, processing_timeout_minutes=10)
            assert cleaner._is_orphan_processing(job) is False


# -- _is_orphan_queued -------------------------------------------------------

class TestIsOrphanQueued:
    def test_within_timeout_not_orphan(self, store, now_patch):
        fixed = make_fixed_dt(2025, 1, 15, 11, 35, 0)
        _make_job(store, status=JobStatus.QUEUED, created_at=fixed)
        cleaner = OrphanJobCleaner(store, queued_timeout_minutes=30)
        jobs = store.list_jobs(status=JobStatus.QUEUED)
        assert cleaner._is_orphan_queued(jobs[0]) is False

    def test_exceeds_timeout_is_orphan(self, store, now_patch):
        fixed = make_fixed_dt(2025, 1, 15, 11, 29, 0)
        _make_job(store, status=JobStatus.QUEUED, created_at=fixed)
        cleaner = OrphanJobCleaner(store, queued_timeout_minutes=30)
        jobs = store.list_jobs(status=JobStatus.QUEUED)
        assert cleaner._is_orphan_queued(jobs[0]) is True


# -- _handle_orphan_job (processing orphans) ---------------------------------

class TestHandleOrphanProcessing:
    @pytest.mark.asyncio
    async def test_requeues_when_retry_below_max(self, store, now_patch):
        job = _make_job(store, status=JobStatus.PROCESSING, started_at=None, retry_count=0)
        cleaner = OrphanJobCleaner(store)
        stats = {"requeued": 0, "failed": 0}
        await cleaner._handle_orphan_job(job, stats)

        updated = store.get_job("job_1")
        assert updated.status == JobStatus.QUEUED
        assert updated.retry_count == 1
        assert updated.progress == 0.0
        assert updated.started_at is None
        assert "reenfileirado" in (updated.error_message or "")
        assert stats["requeued"] == 1

    @pytest.mark.asyncio
    async def test_fails_when_retry_equals_max(self, store, now_patch):
        job = _make_job(store, status=JobStatus.PROCESSING, started_at=None, retry_count=2)
        cleaner = OrphanJobCleaner(store)
        stats = {"requeued": 0, "failed": 0}
        await cleaner._handle_orphan_job(job, stats)

        updated = store.get_job("job_1")
        assert updated.status == JobStatus.FAILED
        assert updated.progress == 0.0
        assert stats["failed"] == 1


# -- _handle_stale_queued_job ------------------------------------------------

class TestHandleStaleQueuedJob:
    @pytest.mark.asyncio
    async def test_marks_failed(self, store, now_patch):
        job = _make_job(store, status=JobStatus.QUEUED)
        cleaner = OrphanJobCleaner(store)
        stats = {"failed": 0}
        await cleaner._handle_stale_queued_job(job, stats)

        updated = store.get_job("job_1")
        assert updated.status == JobStatus.FAILED
        assert updated.progress == 0.0
        assert "fila" in (updated.error_message or "").lower()
        assert stats["failed"] == 1


# -- cleanup_orphans integration ---------------------------------------------

class TestCleanupOrphans:
    @pytest.mark.asyncio
    async def test_empty_store(self, store, now_patch):
        cleaner = OrphanJobCleaner(store)
        result = await cleaner.cleanup_orphans()
        assert result["checked"] == 0
        assert result["orphans_found"] == 0

    @pytest.mark.asyncio
    async def test_detects_and_requeues_processing_orphan(self, store, now_patch):
        _make_job(
            store, "j1", JobStatus.PROCESSING, started_at=None, retry_count=0
        )
        cleaner = OrphanJobCleaner(store)
        result = await cleaner.cleanup_orphans()

        assert result["orphans_found"] == 1
        assert result["requeued"] == 1
        updated = store.get_job("j1")
        assert updated.status == JobStatus.QUEUED

    @pytest.mark.asyncio
    async def test_fails_processing_orphan_exhausted_retries(self, store, now_patch):
        _make_job(
            store, "j2", JobStatus.PROCESSING, started_at=None, retry_count=3
        )
        cleaner = OrphanJobCleaner(store)
        result = await cleaner.cleanup_orphans()

        assert result["orphans_found"] == 1
        assert result["failed"] == 1
        updated = store.get_job("j2")
        assert updated.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_fails_stale_queued(self, store):
        fixed_now_val = make_fixed_dt(2025, 1, 15, 14, 0, 0)
        old_created = make_fixed_dt(2025, 1, 15, 9, 0, 0)
        with patch("common.datetime_utils.now_brazil", return_value=fixed_now_val):
            _make_job(store, "j3", JobStatus.QUEUED, created_at=old_created)
            cleaner = OrphanJobCleaner(store, queued_timeout_minutes=30)
            result = await cleaner.cleanup_orphans()

        assert result["orphans_found"] == 1
        assert result["failed"] == 1
        updated = store.get_job("j3")
        assert updated.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_mixed_processing_and_queued(self, store):
        fixed_now_val = make_fixed_dt(2025, 1, 15, 14, 0, 0)
        old_created = make_fixed_dt(2025, 1, 15, 9, 0, 0)

        with patch("common.datetime_utils.now_brazil", return_value=fixed_now_val):
            _make_job(store, "p1", JobStatus.PROCESSING, started_at=None, retry_count=0)
            _make_job(
                store, "q1", JobStatus.QUEUED, created_at=old_created
            )

            cleaner = OrphanJobCleaner(store, queued_timeout_minutes=30)
            result = await cleaner.cleanup_orphans()

        assert result["checked"] >= 2
        assert result["orphans_found"] >= 2
        assert result["requeued"] >= 1
        assert result["failed"] == 1


# -- DeadLetterQueueManager --------------------------------------------------

class TestDeadLetterQueueManager:
    @pytest.mark.asyncio
    async def test_send_to_dlq(self, store, now_patch):
        job = _make_job(store, status=JobStatus.QUEUED)
        manager = DeadLetterQueueManager(store)
        manager.send_to_dlq(job, "test reason")

        updated = store.get_job("job_1")
        assert updated.status == JobStatus.FAILED
        assert "[DLQ]" in (updated.error_message or "")

    @pytest.mark.asyncio
    async def test_list_dlq_jobs(self, store, now_patch):
        _make_job(store, "f1", status=JobStatus.FAILED)
        _make_job(store, "f2", status=JobStatus.FAILED)
        manager = DeadLetterQueueManager(store)
        dlq = manager.list_dlq_jobs()
        assert len(dlq) == 2

    @pytest.mark.asyncio
    async def test_retry_dlq_success(self, store, now_patch):
        job = _make_job(store, "r1", status=JobStatus.FAILED)
        manager = DeadLetterQueueManager(store)
        ok = manager.retry_dlq_job("r1")
        assert ok is True

        updated = store.get_job("r1")
        assert updated.status == JobStatus.QUEUED
        assert updated.error_message is None

    @pytest.mark.asyncio
    async def test_retry_dlq_not_found(self, store, now_patch):
        manager = DeadLetterQueueManager(store)
        ok = manager.retry_dlq_job("nonexistent")
        assert ok is False


# -- fixture helper ----------------------------------------------------------

@pytest.fixture()
def store():
    return MockJobStore()
