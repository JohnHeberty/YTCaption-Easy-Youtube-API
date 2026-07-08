"""Unit tests for the background video worker."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.models import VideoJob, VideoJobStatus


def _make_job_dict(job_id: str = "rbg_test", status: str = "queued") -> dict:
    return {
        "job_id": job_id,
        "post_id": "post_1",
        "status": status,
        "progress": 0,
        "stages": {
            "generating_audio": {"status": "pending", "progress": 0},
            "generating_images": {"status": "pending", "progress": 0},
            "assembling_video": {"status": "pending", "progress": 0},
        },
        "request": {
            "post_id": "post_1",
            "hook": "Hook",
            "estimated_seconds": 30,
            "narration": [{"t": 0.0, "text": "text"}],
            "scene_suggestions": [{"t": 0.0, "visual": "scene"}],
        },
    }


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.get_next_queued_job = MagicMock(return_value=None)
    store.save_job = MagicMock()
    return store


@pytest.fixture
def worker(mock_store):
    with patch("app.worker.get_video_job_store", return_value=mock_store):
        from app.worker import VideoWorker
        return VideoWorker()


# ---------------------------------------------------------------------------
# _get_next_job
# ---------------------------------------------------------------------------
def test_get_next_job_returns_video_job(worker, mock_store):
    mock_store.get_next_queued_job.return_value = _make_job_dict()
    job = worker._get_next_job()
    assert isinstance(job, VideoJob)
    assert job.job_id == "rbg_test"


def test_get_next_job_returns_none(worker, mock_store):
    mock_store.get_next_queued_job.return_value = None
    job = worker._get_next_job()
    assert job is None


# ---------------------------------------------------------------------------
# _process_job
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_process_job_success(worker, mock_store):
    job = VideoJob(**_make_job_dict())
    from unittest.mock import AsyncMock
    with patch("app.services.pipeline.run_video_pipeline", new_callable=AsyncMock):
        await worker._process_job(job)

    mock_store.save_job.assert_not_called()


@pytest.mark.asyncio
async def test_process_job_failure(worker, mock_store):
    job = VideoJob(**_make_job_dict())
    from unittest.mock import AsyncMock
    with patch("app.services.pipeline.run_video_pipeline", new_callable=AsyncMock, side_effect=Exception("boom")):
        await worker._process_job(job)

    assert job.status == VideoJobStatus.FAILED
    assert "boom" in (job.error or "")
    mock_store.save_job.assert_called_once()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
def test_get_worker_singleton():
    import app.worker as worker_mod
    original = worker_mod._worker
    worker_mod._worker = None
    try:
        with patch("app.worker.get_video_job_store", return_value=MagicMock()):
            w1 = worker_mod.get_worker()
            w2 = worker_mod.get_worker()
            assert w1 is w2
    finally:
        worker_mod._worker = original
