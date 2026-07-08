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


def test_get_next_queued_job(store):
    store.save_job("rbg_1", {"job_id": "rbg_1", "status": "queued", "created_at": 1.0})
    store.save_job("rbg_2", {"job_id": "rbg_2", "status": "completed", "created_at": 2.0})
    job = store.get_next_queued_job()
    assert job is not None
    assert job["job_id"] == "rbg_1"
    assert job["status"] == "queued"


def test_get_next_queued_job_removes_from_queued_set_after_status_change(store):
    store.save_job("rbg_1", {"job_id": "rbg_1", "status": "queued", "created_at": 1.0})
    assert store.get_next_queued_job() is not None

    store.save_job("rbg_1", {"job_id": "rbg_1", "status": "generating_audio", "created_at": 1.0})
    assert store.get_next_queued_job() is None


def test_get_next_queued_job_empty(store):
    assert store.get_next_queued_job() is None


def test_delete_job_removes_from_queued_set(store):
    store.save_job("rbg_1", {"job_id": "rbg_1", "status": "queued"})
    store.delete_job("rbg_1")
    assert store.get_next_queued_job() is None
