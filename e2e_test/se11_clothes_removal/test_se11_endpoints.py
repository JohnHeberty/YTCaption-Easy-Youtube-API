"""E2E tests for SE11 Clothes Removal service — ALL public endpoints."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("APP_NAME", "SE11 Clothes Removal")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/11")
os.environ.setdefault("ENVIRONMENT", "development")

import pytest
from fastapi.testclient import TestClient

from _service_loader import load_app

API_KEY = "test-api-key-2026"
HEADERS = {"X-API-Key": API_KEY}


def _make_png_bytes() -> bytes:
    """Minimal valid PNG (1x1 pixel)."""
    import struct
    import zlib

    signature = b"\x89PNG\r\n\x1a\n"

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    raw = b"\x00\x00\x00\x00\x00"
    idat_data = zlib.compress(raw)

    return (
        signature
        + _chunk(b"IHDR", ihdr_data)
        + _chunk(b"IDAT", idat_data)
        + _chunk(b"IEND", b"")
    )


def _mock_store() -> MagicMock:
    """Create a mock ClothesRemovalJobStore."""
    store = MagicMock()
    store.list_jobs.return_value = []
    store.get_job.return_value = None
    store.save_job.return_value = True
    store.delete_job.return_value = True
    return store


@pytest.fixture
def client():
    with patch("common.redis_utils.resilient_store.ResilientRedisStore._test_connection"):
        app, verify_api_key = load_app("se11-clothes-removal")

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

    def test_health_deep_returns_200(self, client: TestClient):
        r = client.get("/health/deep", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "status" in body

    def test_ping_returns_200(self, client: TestClient):
        r = client.get("/ping", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body.get("pong") is True


# ---------------------------------------------------------------------------
# Metadata Endpoints
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_modes_returns_200(self, client: TestClient):
        r = client.get("/modes", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "modes" in body
        assert isinstance(body["modes"], list)

    def test_detectors_returns_200(self, client: TestClient):
        r = client.get("/detectors", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "detectors" in body
        assert isinstance(body["detectors"], list)

    def test_config_returns_200(self, client: TestClient):
        r = client.get("/config", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)


# ---------------------------------------------------------------------------
# POST /jobs — Create clothes removal job (auth required)
# ---------------------------------------------------------------------------


class TestCreateJob:
    def test_create_job_valid_file(self, client: TestClient):
        png = _make_png_bytes()
        r = client.post(
            "/jobs",
            headers=HEADERS,
            files={"file": ("test_image.png", png, "image/png")},
            data={"mode": "clothes"},
        )
        assert r.status_code == 201
        body = r.json()
        assert "job_id" in body
        assert body["status"] == "queued"

    def test_create_job_no_file_returns_422(self, client: TestClient):
        r = client.post("/jobs", headers=HEADERS)
        assert r.status_code == 422

    def test_create_job_invalid_content_type(self, client: TestClient):
        r = client.post(
            "/jobs",
            headers=HEADERS,
            files={"file": ("test.exe", b"binary", "application/octet-stream")},
            data={"mode": "clothes"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /jobs/nsfw — Create NSFW production job (auth required)
# ---------------------------------------------------------------------------


class TestCreateNSFWJob:
    def test_create_nsfw_job_valid_file(self, client: TestClient):
        png = _make_png_bytes()
        with patch("app.api.routes.check_image_is_ai_generated", return_value=(True, 0.95)):
            r = client.post(
                "/jobs/nsfw",
                headers=HEADERS,
                files={"file": ("test_image.png", png, "image/png")},
            )
        assert r.status_code == 201
        body = r.json()
        assert "job_id" in body
        assert body["status"] == "queued"

    def test_create_nsfw_job_no_file_returns_422(self, client: TestClient):
        r = client.post("/jobs/nsfw", headers=HEADERS)
        assert r.status_code == 422

    def test_create_nsfw_job_rejects_real_photo(self, client: TestClient):
        png = _make_png_bytes()
        with patch("app.api.routes.check_image_is_ai_generated", return_value=(False, 0.10)):
            r = client.post(
                "/jobs/nsfw",
                headers=HEADERS,
                files={"file": ("real_photo.png", png, "image/png")},
            )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /jobs/nsfw-test — Create NSFW test/experimental job (auth required)
# ---------------------------------------------------------------------------


class TestCreateNSFWTestJob:
    def test_create_nsfw_test_job_valid_file(self, client: TestClient):
        png = _make_png_bytes()
        with patch("app.api.routes.check_image_is_ai_generated", return_value=(True, 0.95)):
            r = client.post(
                "/jobs/nsfw-test",
                headers=HEADERS,
                files={"file": ("test_image.png", png, "image/png")},
            )
        assert r.status_code == 201
        body = r.json()
        assert "job_id" in body
        assert body["status"] == "queued"

    def test_create_nsfw_test_job_no_file_returns_422(self, client: TestClient):
        r = client.post("/jobs/nsfw-test", headers=HEADERS)
        assert r.status_code == 422

    def test_create_nsfw_test_job_rejects_real_photo(self, client: TestClient):
        png = _make_png_bytes()
        with patch("app.api.routes.check_image_is_ai_generated", return_value=(False, 0.10)):
            r = client.post(
                "/jobs/nsfw-test",
                headers=HEADERS,
                files={"file": ("real_photo.png", png, "image/png")},
            )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /jobs — List jobs (auth required)
# ---------------------------------------------------------------------------


class TestListJobs:
    def test_list_jobs_returns_200(self, client: TestClient):
        r = client.get("/jobs", headers=HEADERS)
        assert r.status_code == 200

    def test_list_jobs_with_limit(self, client: TestClient):
        r = client.get("/jobs?limit=10&offset=0", headers=HEADERS)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /jobs/{job_id} — Get job status (auth required)
# ---------------------------------------------------------------------------


class TestGetJobStatus:
    def test_get_job_not_found(self, client: TestClient):
        r = client.get("/jobs/cr_nonexistent", headers=HEADERS)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /jobs/{job_id} — Delete job (auth required)
# ---------------------------------------------------------------------------


class TestDeleteJob:
    def test_delete_job_not_found(self, client: TestClient):
        r = client.delete("/jobs/cr_nonexistent", headers=HEADERS)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/download — Download result (auth required)
# ---------------------------------------------------------------------------


class TestDownloadResult:
    def test_download_not_found(self, client: TestClient):
        r = client.get("/jobs/cr_nonexistent/download", headers=HEADERS)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /admin/stats — Admin stats (auth required)
# ---------------------------------------------------------------------------


class TestAdminStats:
    def test_stats_returns_200(self, client: TestClient):
        r = client.get("/admin/stats", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "jobs" in body
        assert "storage" in body


# ---------------------------------------------------------------------------
# POST /admin/cleanup — Admin cleanup (auth required)
# ---------------------------------------------------------------------------


class TestAdminCleanup:
    def test_cleanup_returns_200(self, client: TestClient):
        r = client.post("/admin/cleanup", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "cleaned" in body
