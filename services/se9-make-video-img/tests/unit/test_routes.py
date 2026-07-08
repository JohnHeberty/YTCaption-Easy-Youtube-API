"""Unit tests for API routes."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.models import CreateVideoRequest, NarrationSegment, SceneSuggestion


def _make_request_dict(**overrides) -> dict:
    defaults = dict(
        post_id="post_1",
        hook="Hook text",
        estimated_seconds=30,
        narration=[{"t": 0.0, "text": "Olá mundo"}],
        scene_suggestions=[{"t": 0.0, "visual": "A sunset"}],
    )
    defaults.update(overrides)
    return defaults


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.get_job = MagicMock(return_value=None)
    store.save_job = MagicMock()
    store.delete_job = MagicMock()
    store.list_jobs = MagicMock(return_value=[])
    return store


@pytest.fixture
def client(mock_store):
    with patch("app.api.routes.store", mock_store):
        with patch("app.api.routes.get_worker") as mock_get_worker:
            mock_worker = MagicMock()
            mock_get_worker.return_value = mock_worker
            from app.api.routes import router
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            yield TestClient(app), mock_store, mock_worker


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------
def test_root(client):
    tc, _, _ = client
    resp = tc.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "make-video-img"
    assert "POST /jobs" in data["endpoints"]


# ---------------------------------------------------------------------------
# Create job
# ---------------------------------------------------------------------------
def test_create_job(client):
    tc, store, worker = client
    payload = _make_request_dict()
    resp = tc.post("/jobs", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["job_id"].startswith("rbg_")
    assert data["post_id"] == "post_1"
    assert data["scenes_count"] == 1
    store.save_job.assert_called_once()
    worker.start.assert_called_once()


# ---------------------------------------------------------------------------
# Get job status
# ---------------------------------------------------------------------------
def test_get_job_status(client):
    tc, store, _ = client
    store.get_job.return_value = {
        "job_id": "rbg_test",
        "status": "completed",
        "progress": 100.0,
        "stages": {},
        "created_at": "2026-01-01T00:00:00",
    }
    resp = tc.get("/jobs/rbg_test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == "rbg_test"
    assert data["status"] == "completed"


def test_get_job_status_404(client):
    tc, store, _ = client
    store.get_job.return_value = None
    resp = tc.get("/jobs/rbg_nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete job
# ---------------------------------------------------------------------------
def test_delete_job(client):
    tc, store, _ = client
    store.get_job.return_value = {"job_id": "rbg_del", "status": "completed"}
    with patch("app.api.routes.os.path.exists", return_value=True):
        with patch("app.api.routes.shutil.rmtree"):
            resp = tc.delete("/jobs/rbg_del")
    assert resp.status_code == 200
    assert "deleted" in resp.json()["detail"]
    store.delete_job.assert_called_once_with("rbg_del")


def test_delete_job_404(client):
    tc, store, _ = client
    store.get_job.return_value = None
    resp = tc.delete("/jobs/rbg_nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# List jobs
# ---------------------------------------------------------------------------
def test_list_jobs(client):
    tc, store, _ = client
    store.list_jobs.return_value = [
        {"job_id": "rbg_1", "status": "queued", "progress": 0, "post_id": "p1", "created_at": "2026-01-01"},
        {"job_id": "rbg_2", "status": "completed", "progress": 100, "post_id": "p2", "created_at": "2026-01-02"},
    ]
    resp = tc.get("/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["jobs"]) == 2
    assert data["jobs"][0]["job_id"] == "rbg_1"


def test_list_jobs_empty(client):
    tc, store, _ = client
    store.list_jobs.return_value = []
    resp = tc.get("/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["jobs"] == []
