"""E2E tests for SE9 Make Video IMG service — ALL public endpoints."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

os.environ.setdefault("APP_NAME", "SE9 Make Video IMG")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/9")
os.environ.setdefault("ENVIRONMENT", "development")

import pytest
from fastapi.testclient import TestClient

from _service_loader import load_app

API_KEY = "test-api-key-2026"
HEADERS = {"X-API-Key": API_KEY}


def _valid_job_payload() -> dict:
    """Minimal valid CreateVideoRequest payload."""
    return {
        "post_id": "e2e_test_001",
        "hook": "E2E test hook for video generation",
        "estimated_seconds": 15,
        "narration": [
            {"t": 0, "text": "This is a test narration."},
            {"t": 3, "text": "Second line of narration."},
        ],
        "scene_suggestions": [
            {
                "t": 0,
                "visual": "Establishing shot, test environment.",
                "negative_prompt": "blurry, low quality",
                "camera_movement": "static",
                "transition": "dissolve",
            },
            {
                "t": 3,
                "visual": "Close-up shot, soft lighting.",
                "camera_movement": "slow_push_in",
            },
        ],
    }


def _mock_store() -> MagicMock:
    """Create a mock VideoJobStore."""
    store = MagicMock()
    store.list_jobs.return_value = []
    store.get_job.return_value = None
    store.delete_job.return_value = True
    return store


@pytest.fixture
def client():
    with patch("common.redis_utils.resilient_store.ResilientRedisStore._test_connection"):
        app, verify_api_key = load_app("se9-make-video-img")

        async def _skip_auth() -> None:
            return None

        app.dependency_overrides[verify_api_key] = _skip_auth

        mock_store = _mock_store()
        with patch("app.api.routes.store", mock_store), \
             patch("app.api.admin_routes.store", mock_store), \
             patch("app.api.download_routes.store", mock_store), \
             patch("app.worker.get_worker") as mock_get_worker:
            worker = MagicMock()
            mock_get_worker.return_value = worker

            with TestClient(app, raise_server_exceptions=False) as c:
                yield c

        app.dependency_overrides.pop(verify_api_key, None)


# ---------------------------------------------------------------------------
# GET / — Root
# ---------------------------------------------------------------------------


class TestRoot:
    def test_get_root_returns_200(self, client: TestClient):
        r = client.get("/", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "service" in body
        assert "version" in body
        assert "endpoints" in body


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_200(self, client: TestClient):
        r = client.get("/health", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "status" in body

    def test_ping_returns_200(self, client: TestClient):
        r = client.get("/ping", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body.get("pong") is True


# ---------------------------------------------------------------------------
# Config / Metadata
# ---------------------------------------------------------------------------


class TestConfig:
    def test_config_returns_200(self, client: TestClient):
        r = client.get("/config", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "defaults" in body or "service" in body

    def test_transitions_returns_200(self, client: TestClient):
        r = client.get("/transitions", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "transitions" in body
        assert isinstance(body["transitions"], list)

    def test_camera_movements_returns_200(self, client: TestClient):
        r = client.get("/camera-movements", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "movements" in body
        assert "mapping" in body

    def test_voices_returns_200(self, client: TestClient):
        with patch("app.api.routes.SE7Client") as MockSE7:
            instance = AsyncMock()
            instance.list_voices = AsyncMock(return_value=[
                {"id": "builtin_feminino", "name": "Feminino"},
                {"id": "builtin_masculino", "name": "Masculino"},
            ])
            instance.close = AsyncMock()
            MockSE7.return_value = instance
            r = client.get("/voices", headers=HEADERS)
            assert r.status_code == 200
            body = r.json()
            assert "voices" in body
            assert len(body["voices"]) >= 2


# ---------------------------------------------------------------------------
# POST /jobs — Create
# ---------------------------------------------------------------------------


class TestCreateJob:
    def test_create_job_valid_payload(self, client: TestClient):
        r = client.post("/jobs", headers=HEADERS, json=_valid_job_payload())
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        body = r.json()
        assert "job_id" in body
        assert body["job_id"].startswith("rbg_")
        assert body["status"] == "queued"

    def test_create_job_empty_body_returns_422(self, client: TestClient):
        r = client.post("/jobs", headers=HEADERS)
        assert r.status_code == 422

    def test_create_job_missing_required_field_returns_422(self, client: TestClient):
        payload = {"post_id": "test123"}
        r = client.post("/jobs", headers=HEADERS, json=payload)
        assert r.status_code == 422

    def test_create_job_empty_scenes_returns_422(self, client: TestClient):
        payload = _valid_job_payload()
        payload["scene_suggestions"] = []
        r = client.post("/jobs", headers=HEADERS, json=payload)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /jobs — List
# ---------------------------------------------------------------------------


class TestListJobs:
    def test_list_jobs_returns_200(self, client: TestClient):
        r = client.get("/jobs", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "jobs" in body or isinstance(body, list)

    def test_list_jobs_with_limit(self, client: TestClient):
        r = client.get("/jobs?limit=10&offset=0", headers=HEADERS)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /jobs/{job_id} — Status
# ---------------------------------------------------------------------------


class TestGetJobStatus:
    def test_get_job_not_found(self, client: TestClient):
        r = client.get("/jobs/rbg_nonexistent", headers=HEADERS)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /jobs/{job_id}
# ---------------------------------------------------------------------------


class TestDeleteJob:
    def test_delete_job_not_found(self, client: TestClient):
        r = client.delete("/jobs/rbg_nonexistent", headers=HEADERS)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /download/{job_id}
# ---------------------------------------------------------------------------


class TestDownloadVideo:
    def test_download_not_found(self, client: TestClient):
        r = client.get("/download/rbg_nonexistent", headers=HEADERS)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /admin/stats
# ---------------------------------------------------------------------------


class TestAdminStats:
    def test_stats_returns_200(self, client: TestClient):
        r = client.get("/admin/stats", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "jobs" in body
        assert "total" in body["jobs"]


# ---------------------------------------------------------------------------
# POST /admin/cleanup
# ---------------------------------------------------------------------------


class TestAdminCleanup:
    def test_cleanup_returns_200(self, client: TestClient):
        r = client.post("/admin/cleanup", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "detail" in body
