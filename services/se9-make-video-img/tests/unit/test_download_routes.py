"""Unit tests for download route."""
from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.models import VideoJobStatus


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.get_job = MagicMock(return_value=None)
    return store


@pytest.fixture
def client(mock_store):
    with patch("app.api.download_routes.store", mock_store):
        from app.api.download_routes import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        yield TestClient(app), mock_store


def test_download_success(client):
    tc, store = client
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"fake video data")
        tmp_path = f.name
    try:
        store.get_job.return_value = {
            "job_id": "rbg_ok",
            "status": "completed",
            "video_path": tmp_path,
        }
        resp = tc.get("/download/rbg_ok")
        assert resp.status_code == 200
    finally:
        os.unlink(tmp_path)


def test_download_404(client):
    tc, store = client
    store.get_job.return_value = None
    resp = tc.get("/download/rbg_nonexistent")
    assert resp.status_code == 404


def test_download_not_completed(client):
    tc, store = client
    store.get_job.return_value = {
        "job_id": "rbg_q",
        "status": "queued",
        "video_path": None,
    }
    resp = tc.get("/download/rbg_q")
    assert resp.status_code == 400
    assert "not completed" in resp.json()["detail"]


def test_download_file_not_found(client):
    tc, store = client
    store.get_job.return_value = {
        "job_id": "rbg_done",
        "status": "completed",
        "video_path": "/tmp/nonexistent.mp4",
    }
    with patch("app.api.download_routes.os.path.exists", return_value=False):
        resp = tc.get("/download/rbg_done")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
