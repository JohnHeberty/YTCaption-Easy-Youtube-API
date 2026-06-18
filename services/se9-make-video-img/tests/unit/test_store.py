"""Unit tests for the video store."""
import pytest
from app.infrastructure.redis_store import VideoJobStore, _FakeRedis


@pytest.fixture
def fake_redis():
    return _FakeRedis()


@pytest.fixture
def store(fake_redis):
    s = VideoJobStore()
    s.redis = fake_redis
    return s


def test_save_and_get_job(store):
    job_data = {"job_id": "rbg_test", "status": "queued"}
    store.save_job("rbg_test", job_data)
    result = store.get_job("rbg_test")
    assert result is not None
    assert result["job_id"] == "rbg_test"
    assert result["status"] == "queued"


def test_get_nonexistent_job(store):
    result = store.get_job("rbg_nonexistent")
    assert result is None


def test_update_job(store):
    job_data = {"job_id": "rbg_test", "status": "queued", "progress": 0}
    store.save_job("rbg_test", job_data)
    store.update_job("rbg_test", {"status": "processing", "progress": 50})
    result = store.get_job("rbg_test")
    assert result["status"] == "processing"
    assert result["progress"] == 50


def test_delete_job(store):
    job_data = {"job_id": "rbg_test", "status": "queued"}
    store.save_job("rbg_test", job_data)
    store.delete_job("rbg_test")
    assert store.get_job("rbg_test") is None


def test_list_jobs(store):
    store.save_job("rbg_1", {"job_id": "rbg_1", "status": "queued"})
    store.save_job("rbg_2", {"job_id": "rbg_2", "status": "completed"})
    jobs = store.list_jobs()
    assert len(jobs) == 2
