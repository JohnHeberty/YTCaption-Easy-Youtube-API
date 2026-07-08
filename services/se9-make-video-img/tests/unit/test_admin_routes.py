"""Unit tests for admin routes."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.list_jobs = MagicMock(return_value=[])
    store.delete_job = MagicMock()
    return store


@pytest.fixture
def client(mock_store):
    with patch("app.api.admin_routes.store", mock_store):
        from app.api.admin_routes import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        yield TestClient(app), mock_store


def test_stats(client):
    tc, store = client
    store.list_jobs.return_value = [
        {"status": "completed"},
        {"status": "completed"},
        {"status": "failed"},
        {"status": "queued"},
    ]
    with patch("app.api.admin_routes.os.path.exists", return_value=True):
        with patch("app.api.admin_routes.shutil.disk_usage", return_value=(100 * 1024**3, 40 * 1024**3, 60 * 1024**3)):
            resp = tc.get("/admin/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["jobs"]["total"] == 4
    assert data["jobs"]["by_status"]["completed"] == 2
    assert data["jobs"]["by_status"]["failed"] == 1


def test_cleanup_removes_failed(client):
    tc, store = client
    store.list_jobs.return_value = [
        {"job_id": "rbg_fail1", "status": "failed"},
        {"job_id": "rbg_ok", "status": "completed"},
    ]
    with patch("app.api.admin_routes.os.path.exists", return_value=True):
        with patch("app.api.admin_routes.shutil.rmtree"):
            resp = tc.post("/admin/cleanup")
    assert resp.status_code == 200
    assert "1" in resp.json()["detail"]
    store.delete_job.assert_called_once_with("rbg_fail1")


def test_cleanup_skips_completed(client):
    tc, store = client
    store.list_jobs.return_value = [
        {"job_id": "rbg_ok", "status": "completed"},
    ]
    with patch("app.api.admin_routes.os.path.exists", return_value=True):
        with patch("app.api.admin_routes.shutil.rmtree"):
            resp = tc.post("/admin/cleanup")
    assert resp.status_code == 200
    assert "0" in resp.json()["detail"]
    store.delete_job.assert_not_called()


def test_cleanup_empty(client):
    tc, store = client
    store.list_jobs.return_value = []
    resp = tc.post("/admin/cleanup")
    assert resp.status_code == 200
    assert "0" in resp.json()["detail"]
