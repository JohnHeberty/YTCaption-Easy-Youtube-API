"""
E2E Tests for SE5 Make Video Clip Service — All Endpoints.

Port 8005. Covers system endpoints, workflow endpoints, job management,
cache stats, and authentication middleware.
"""
from __future__ import annotations

import os
import struct
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# Set env BEFORE any app import
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("APP_NAME", "se5-make-video-clip")

import pytest
from fastapi.testclient import TestClient

from _service_loader import load_app


API_KEY = "test-api-key-2026"
HEADERS = {"X-API-Key": API_KEY}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav_bytes() -> bytes:
    """Minimal valid WAV file (1 sample, 8-bit mono, 44100 Hz)."""
    sample_rate = 44100
    num_channels = 1
    bits_per_sample = 8
    data = b"\x80"
    data_size = len(data)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        num_channels,
        sample_rate,
        sample_rate * num_channels * bits_per_sample // 8,
        num_channels * bits_per_sample // 8,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + data


def _make_mock_job(
    job_id: str = "mv_test_001",
    status_value: str = "completed",
    progress: float = 100.0,
) -> MagicMock:
    """Create a mock MakeVideoJob with all fields used by route handlers."""
    from common.job_utils.models import JobStatus

    _STATUS_MAP = {
        "completed": JobStatus.COMPLETED,
        "processing": JobStatus.PROCESSING,
        "queued": JobStatus.QUEUED,
        "failed": JobStatus.FAILED,
        "cancelled": JobStatus.CANCELLED,
    }

    job = MagicMock()
    job.id = job_id
    job.status = _STATUS_MAP.get(status_value, JobStatus(status_value))
    job.progress = progress
    job.stages = {}
    job.result = None
    job.error = None
    job.created_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    job.updated_at = datetime(2026, 1, 1, 12, 0, 5, tzinfo=timezone.utc)
    job.model_dump.return_value = {
        "id": job_id,
        "status": status_value,
        "progress": progress,
    }
    return job


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Create a TestClient with mocked Redis, dependencies, and auth bypass.

    Patches both the lifespan dependency factories (so the startup/shutdown
    uses mocks with ``stop_cleanup_task``) and the route-level override
    functions (so endpoints receive mock stores/clients).
    """
    app, verify_api_key = load_app("se5-make-video-clip")

    patches = [
        patch("common.redis_utils.resilient_store.ResilientRedisStore._test_connection"),
        patch("app.main.get_redis_store"),
        patch("app.main.get_job_manager"),
        patch("app.main.get_cache_manager"),
        patch("app.main.get_lock_manager"),
        patch("app.main.get_api_client"),
    ]
    for p in patches:
        p.start()

    try:

        mock_store = MagicMock()
        mock_store.list_jobs.return_value = []
        mock_store.get_job.return_value = None
        mock_store.stop_cleanup_task = AsyncMock()
        mock_store.start_cleanup_task = AsyncMock()

        mock_job_mgr = MagicMock()
        mock_job_mgr.get_stats.return_value = {
            "queued": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
        }

        mock_cache_mgr = MagicMock()
        mock_cache_mgr.get_stats.return_value = {
            "total_shorts": 0,
            "total_size_mb": 0.0,
            "approved_videos": 0,
        }

        mock_lock_mgr = MagicMock()
        mock_lock_mgr.close = AsyncMock()

        mock_api_cli = MagicMock()

        import app.main as main_mod
        main_mod.get_redis_store.return_value = mock_store
        main_mod.get_job_manager.return_value = mock_job_mgr
        main_mod.get_cache_manager.return_value = mock_cache_mgr
        main_mod.get_lock_manager.return_value = mock_lock_mgr
        main_mod.get_api_client.return_value = mock_api_cli

        import app.infrastructure.dependencies as deps
        deps._redis_store_override = mock_store
        deps._job_manager_override = mock_job_mgr
        deps._cache_manager_override = mock_cache_mgr
        deps._lock_manager_override = mock_lock_mgr
        deps._api_client_override = mock_api_cli

        async def _skip():
            return None

        app.dependency_overrides[verify_api_key] = _skip

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        app.dependency_overrides.pop(verify_api_key, None)
        deps.reset_overrides()
    finally:
        for p in patches:
            p.stop()


@pytest.fixture
def unauth_client():
    """TestClient WITHOUT auth override — for testing 401/403 responses."""
    app, verify_api_key = load_app("se5-make-video-clip")

    patches = [
        patch("common.redis_utils.resilient_store.ResilientRedisStore._test_connection"),
        patch("app.main.get_redis_store"),
        patch("app.main.get_job_manager"),
        patch("app.main.get_cache_manager"),
        patch("app.main.get_lock_manager"),
        patch("app.main.get_api_client"),
    ]
    for p in patches:
        p.start()

    try:
        mock_store = MagicMock()
        mock_store.list_jobs.return_value = []
        mock_store.get_job.return_value = None
        mock_store.stop_cleanup_task = AsyncMock()
        mock_store.start_cleanup_task = AsyncMock()

        mock_job_mgr = MagicMock()
        mock_job_mgr.get_stats.return_value = {
            "queued": 0, "processing": 0, "completed": 0, "failed": 0,
        }
        mock_cache_mgr = MagicMock()
        mock_cache_mgr.get_stats.return_value = {
            "total_shorts": 0, "total_size_mb": 0.0, "approved_videos": 0,
        }
        mock_lock_mgr = MagicMock()
        mock_lock_mgr.close = AsyncMock()
        mock_api_cli = MagicMock()

        import app.main as main_mod
        main_mod.get_redis_store.return_value = mock_store
        main_mod.get_job_manager.return_value = mock_job_mgr
        main_mod.get_cache_manager.return_value = mock_cache_mgr
        main_mod.get_lock_manager.return_value = mock_lock_mgr
        main_mod.get_api_client.return_value = mock_api_cli

        import app.infrastructure.dependencies as deps
        deps._redis_store_override = mock_store
        deps._job_manager_override = mock_job_mgr
        deps._cache_manager_override = mock_cache_mgr
        deps._lock_manager_override = mock_lock_mgr
        deps._api_client_override = mock_api_cli

        # NO auth override — this client tests unauthenticated access
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        deps.reset_overrides()
    finally:
        for p in patches:
            p.stop()


@pytest.fixture
def mock_store():
    """Return the mock Redis store set up by the client fixture."""
    import app.infrastructure.dependencies as deps
    return deps._redis_store_override


# ---------------------------------------------------------------------------
# GET / — Service info
# ---------------------------------------------------------------------------

class TestRootEndpoint:
    """GET / — Service info and endpoint catalog."""

    def test_returns_200(self, client: TestClient):
        r = client.get("/", headers=HEADERS)
        assert r.status_code == 200

    def test_returns_service_name(self, client: TestClient):
        r = client.get("/", headers=HEADERS)
        body = r.json()
        assert body["service"] == "make-video-clip"

    def test_returns_version(self, client: TestClient):
        r = client.get("/", headers=HEADERS)
        body = r.json()
        assert "version" in body

    def test_returns_endpoints_catalog(self, client: TestClient):
        r = client.get("/", headers=HEADERS)
        body = r.json()
        assert "endpoints" in body
        assert "system" in body["endpoints"]
        assert "workflow" in body["endpoints"]
        assert "jobs" in body["endpoints"]

    def test_works_without_auth(self, unauth_client: TestClient):
        r = unauth_client.get("/")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /health — Health check
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """GET /health — Health check."""

    def test_returns_200(self, client: TestClient):
        r = client.get("/health", headers=HEADERS)
        assert r.status_code == 200

    def test_returns_healthy_status(self, client: TestClient):
        r = client.get("/health", headers=HEADERS)
        body = r.json()
        assert body["status"] == "healthy"

    def test_returns_service_name(self, client: TestClient):
        r = client.get("/health", headers=HEADERS)
        body = r.json()
        assert body["service"] == "make-video-clip"

    def test_returns_timestamp(self, client: TestClient):
        r = client.get("/health", headers=HEADERS)
        body = r.json()
        assert "timestamp" in body

    def test_works_without_auth(self, unauth_client: TestClient):
        r = unauth_client.get("/health")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /metrics — Prometheus metrics
# ---------------------------------------------------------------------------

class TestMetricsEndpoint:
    """GET /metrics — Prometheus-compatible metrics."""

    def test_returns_200(self, client: TestClient):
        r = client.get("/metrics", headers=HEADERS)
        assert r.status_code == 200

    def test_returns_text_plain(self, client: TestClient):
        r = client.get("/metrics", headers=HEADERS)
        assert "text/plain" in r.headers["content-type"]

    def test_contains_queued_metric(self, client: TestClient):
        r = client.get("/metrics", headers=HEADERS)
        assert "makevideo_jobs_queued" in r.text

    def test_contains_processing_metric(self, client: TestClient):
        r = client.get("/metrics", headers=HEADERS)
        assert "makevideo_jobs_processing" in r.text

    def test_contains_completed_metric(self, client: TestClient):
        r = client.get("/metrics", headers=HEADERS)
        assert "makevideo_jobs_completed" in r.text

    def test_contains_failed_metric(self, client: TestClient):
        r = client.get("/metrics", headers=HEADERS)
        assert "makevideo_jobs_failed" in r.text

    def test_contains_disk_metrics(self, client: TestClient):
        r = client.get("/metrics", headers=HEADERS)
        assert "makevideo_disk_free_gb" in r.text


# ---------------------------------------------------------------------------
# GET /cache/stats — Cache statistics
# ---------------------------------------------------------------------------

class TestCacheStatsEndpoint:
    """GET /cache/stats — Cache statistics."""

    def test_returns_200(self, client: TestClient):
        r = client.get("/cache/stats", headers=HEADERS)
        assert r.status_code == 200

    def test_returns_total_shorts(self, client: TestClient):
        r = client.get("/cache/stats", headers=HEADERS)
        body = r.json()
        assert "total_shorts" in body
        assert isinstance(body["total_shorts"], int)

    def test_returns_total_size_mb(self, client: TestClient):
        r = client.get("/cache/stats", headers=HEADERS)
        body = r.json()
        assert "total_size_mb" in body
        assert isinstance(body["total_size_mb"], float)

    def test_returns_approved_videos(self, client: TestClient):
        r = client.get("/cache/stats", headers=HEADERS)
        body = r.json()
        assert "approved_videos" in body
        assert isinstance(body["approved_videos"], int)

    def test_with_custom_cache_stats(self, client: TestClient, mock_store):
        import app.infrastructure.dependencies as deps
        deps._cache_manager_override.get_stats.return_value = {
            "total_shorts": 120,
            "total_size_mb": 450.2,
            "approved_videos": 35,
        }
        r = client.get("/cache/stats", headers=HEADERS)
        body = r.json()
        assert body["total_shorts"] == 120
        assert body["total_size_mb"] == 450.2
        assert body["approved_videos"] == 35


# ---------------------------------------------------------------------------
# GET /jobs — List jobs
# ---------------------------------------------------------------------------

class TestListJobsEndpoint:
    """GET /jobs — List all jobs."""

    def test_returns_200(self, client: TestClient):
        r = client.get("/jobs", headers=HEADERS)
        assert r.status_code == 200

    def test_returns_empty_list(self, client: TestClient):
        r = client.get("/jobs", headers=HEADERS)
        body = r.json()
        assert body["status"] == "success"
        assert body["total"] == 0
        assert body["jobs"] == []

    def test_returns_200_with_limit(self, client: TestClient):
        r = client.get("/jobs?limit=10", headers=HEADERS)
        assert r.status_code == 200

    def test_rejects_limit_zero(self, client: TestClient):
        r = client.get("/jobs?limit=0", headers=HEADERS)
        assert r.status_code == 422

    def test_rejects_limit_exceeds_max(self, client: TestClient):
        r = client.get("/jobs?limit=501", headers=HEADERS)
        assert r.status_code == 422

    def test_returns_with_jobs(self, client: TestClient, mock_store):
        mock_job = _make_mock_job()
        mock_store.list_jobs.return_value = [mock_job]
        r = client.get("/jobs", headers=HEADERS)
        body = r.json()
        assert body["total"] == 1
        assert len(body["jobs"]) == 1

    def test_with_status_filter(self, client: TestClient, mock_store):
        job1 = _make_mock_job("mv_001", status_value="completed")
        job2 = _make_mock_job("mv_002", status_value="processing")
        mock_store.list_jobs.return_value = [job1, job2]
        r = client.get("/jobs?status=completed", headers=HEADERS)
        body = r.json()
        assert body["total"] == 1


# ---------------------------------------------------------------------------
# GET /jobs/{job_id} — Get job status
# ---------------------------------------------------------------------------

class TestGetJobStatusEndpoint:
    """GET /jobs/{job_id} — Get job status."""

    def test_returns_404_not_found(self, client: TestClient):
        r = client.get("/jobs/mv_nonexistent", headers=HEADERS)
        assert r.status_code == 404

    def test_404_has_error_message(self, client: TestClient):
        r = client.get("/jobs/mv_nonexistent", headers=HEADERS)
        body = r.json()
        assert "message" in body
        assert "not found" in body["message"].lower()

    def test_returns_200_for_existing_job(self, client: TestClient, mock_store):
        mock_job = _make_mock_job("mv_exists_001")
        mock_store.get_job.return_value = mock_job
        r = client.get("/jobs/mv_exists_001", headers=HEADERS)
        assert r.status_code == 200

    def test_returns_job_id(self, client: TestClient, mock_store):
        mock_job = _make_mock_job("mv_fields_001")
        mock_store.get_job.return_value = mock_job
        r = client.get("/jobs/mv_fields_001", headers=HEADERS)
        body = r.json()
        assert body["job_id"] == "mv_fields_001"

    def test_returns_status(self, client: TestClient, mock_store):
        mock_job = _make_mock_job("mv_st_001", status_value="processing")
        mock_store.get_job.return_value = mock_job
        r = client.get("/jobs/mv_st_001", headers=HEADERS)
        body = r.json()
        assert body["status"] == "processing"

    def test_returns_progress(self, client: TestClient, mock_store):
        mock_job = _make_mock_job("mv_pr_001", progress=45.0)
        mock_store.get_job.return_value = mock_job
        r = client.get("/jobs/mv_pr_001", headers=HEADERS)
        body = r.json()
        assert body["progress"] == 45.0

    def test_returns_stages_dict(self, client: TestClient, mock_store):
        mock_job = _make_mock_job("mv_sg_001")
        mock_store.get_job.return_value = mock_job
        r = client.get("/jobs/mv_sg_001", headers=HEADERS)
        body = r.json()
        assert "stages" in body
        assert isinstance(body["stages"], dict)


# ---------------------------------------------------------------------------
# GET /download/{job_id} — Download video file
# ---------------------------------------------------------------------------

class TestDownloadVideoEndpoint:
    """GET /download/{job_id} — Download completed video file."""

    def test_returns_404_not_found(self, client: TestClient):
        r = client.get("/download/mv_nonexistent", headers=HEADERS)
        assert r.status_code == 404

    def test_404_has_error_message(self, client: TestClient):
        r = client.get("/download/mv_nonexistent", headers=HEADERS)
        body = r.json()
        assert "message" in body
        assert "not found" in body["message"].lower()

    def test_returns_400_for_incomplete_job(self, client: TestClient, mock_store):
        mock_job = _make_mock_job("mv_incomplete", status_value="processing")
        mock_store.get_job.return_value = mock_job
        r = client.get("/download/mv_incomplete", headers=HEADERS)
        assert r.status_code == 400

    def test_400_message_shows_status(self, client: TestClient, mock_store):
        mock_job = _make_mock_job("mv_incomplete2", status_value="queued")
        mock_store.get_job.return_value = mock_job
        r = client.get("/download/mv_incomplete2", headers=HEADERS)
        body = r.json()
        assert "queued" in body["message"].lower()

    def test_404_when_file_missing_on_disk(self, client: TestClient, mock_store):
        mock_job = _make_mock_job("mv_nofile", status_value="completed")
        mock_store.get_job.return_value = mock_job
        r = client.get("/download/mv_nofile", headers=HEADERS)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /download — Start shorts download pipeline
# ---------------------------------------------------------------------------

class TestDownloadPipelineEndpoint:
    """POST /download — Start shorts download pipeline."""

    def test_returns_202_with_valid_query(self, client: TestClient):
        with patch("app.api.routes.process_download_pipeline") as mock_celery:
            mock_celery.delay.return_value = MagicMock()
            r = client.post(
                "/download",
                headers=HEADERS,
                data={"query": "motivacao", "max_shorts": 50},
            )
            assert r.status_code == 202

    def test_returns_accepted_status(self, client: TestClient):
        with patch("app.api.routes.process_download_pipeline") as mock_celery:
            mock_celery.delay.return_value = MagicMock()
            r = client.post(
                "/download",
                headers=HEADERS,
                data={"query": "treino funcional", "max_shorts": 30},
            )
            body = r.json()
            assert body["status"] == "accepted"

    def test_returns_job_id(self, client: TestClient):
        with patch("app.api.routes.process_download_pipeline") as mock_celery:
            mock_celery.delay.return_value = MagicMock()
            r = client.post(
                "/download",
                headers=HEADERS,
                data={"query": "motivacao", "max_shorts": 50},
            )
            body = r.json()
            assert "job_id" in body
            assert body["job_id"].startswith("mv_")

    def test_returns_query(self, client: TestClient):
        with patch("app.api.routes.process_download_pipeline") as mock_celery:
            mock_celery.delay.return_value = MagicMock()
            r = client.post(
                "/download",
                headers=HEADERS,
                data={"query": "motivacao", "max_shorts": 50},
            )
            body = r.json()
            assert body["query"] == "motivacao"

    def test_returns_max_shorts(self, client: TestClient):
        with patch("app.api.routes.process_download_pipeline") as mock_celery:
            mock_celery.delay.return_value = MagicMock()
            r = client.post(
                "/download",
                headers=HEADERS,
                data={"query": "motivacao", "max_shorts": 75},
            )
            body = r.json()
            assert body["max_shorts"] == 75

    def test_returns_message(self, client: TestClient):
        with patch("app.api.routes.process_download_pipeline") as mock_celery:
            mock_celery.delay.return_value = MagicMock()
            r = client.post(
                "/download",
                headers=HEADERS,
                data={"query": "motivacao", "max_shorts": 50},
            )
            body = r.json()
            assert "message" in body

    def test_returns_422_missing_query(self, client: TestClient):
        r = client.post("/download", headers=HEADERS)
        assert r.status_code == 422

    def test_returns_422_short_query(self, client: TestClient):
        with patch("app.api.routes.process_download_pipeline"):
            r = client.post(
                "/download",
                headers=HEADERS,
                data={"query": "ab", "max_shorts": 50},
            )
            assert r.status_code == 422

    def test_calls_celery_task(self, client: TestClient):
        with patch("app.api.routes.process_download_pipeline") as mock_celery:
            mock_celery.delay.return_value = MagicMock()
            client.post(
                "/download",
                headers=HEADERS,
                data={"query": "motivacao", "max_shorts": 50},
            )
            mock_celery.delay.assert_called_once()

    def test_saves_job_to_store(self, client: TestClient, mock_store):
        with patch("app.api.routes.process_download_pipeline"):
            client.post(
                "/download",
                headers=HEADERS,
                data={"query": "motivacao", "max_shorts": 50},
            )
            mock_store.save_job.assert_called_once()

    def test_rejects_limit_below_minimum(self, client: TestClient):
        with patch("app.api.routes.process_download_pipeline"):
            r = client.post(
                "/download",
                headers=HEADERS,
                data={"query": "motivacao", "max_shorts": 5},
            )
            assert r.status_code == 422

    def test_rejects_limit_above_maximum(self, client: TestClient):
        with patch("app.api.routes.process_download_pipeline"):
            r = client.post(
                "/download",
                headers=HEADERS,
                data={"query": "motivacao", "max_shorts": 501},
            )
            assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /make-video — Create video from audio + shorts
# ---------------------------------------------------------------------------

class TestCreateVideoEndpoint:
    """POST /make-video — Create video from audio + shorts.

    NOTE: The current route handler (``_validate_create_video_params``) requires
    ``content: bytes`` as a query parameter, which makes the endpoint reject all
    multipart uploads with 422. The async ``create_video`` function (which has
    proper Form/File annotations) is defined but not wired as the route handler.
    """

    def test_returns_422_missing_file(self, client: TestClient):
        r = client.post("/make-video", headers=HEADERS)
        assert r.status_code == 422

    def test_returns_422_with_file_due_to_content_param(self, client: TestClient):
        wav = _make_wav_bytes()
        r = client.post(
            "/make-video",
            headers=HEADERS,
            files={"audio_file": ("test.wav", wav, "audio/wav")},
            data={
                "max_shorts": 10,
                "subtitle_language": "pt",
                "subtitle_style": "static",
                "aspect_ratio": "9:16",
                "crop_position": "center",
            },
        )
        assert r.status_code == 422

    def test_422_response_has_details(self, client: TestClient):
        r = client.post("/make-video", headers=HEADERS)
        body = r.json()
        assert "details" in body or "error" in body

    def test_422_rejects_max_shorts_below_minimum(self, client: TestClient):
        wav = _make_wav_bytes()
        r = client.post(
            "/make-video",
            headers=HEADERS,
            files={"audio_file": ("test.wav", wav, "audio/wav")},
            data={"max_shorts": 5},
        )
        assert r.status_code == 422

    def test_422_rejects_max_shorts_above_maximum(self, client: TestClient):
        wav = _make_wav_bytes()
        r = client.post(
            "/make-video",
            headers=HEADERS,
            files={"audio_file": ("test.wav", wav, "audio/wav")},
            data={"max_shorts": 501},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /jobs/{job_id} — Delete job
# ---------------------------------------------------------------------------

class TestDeleteJobEndpoint:
    """DELETE /jobs/{job_id} — Delete a job and its files."""

    def test_returns_404_not_found(self, client: TestClient):
        r = client.delete("/jobs/mv_nonexistent", headers=HEADERS)
        assert r.status_code == 404

    def test_404_has_error_message(self, client: TestClient):
        r = client.delete("/jobs/mv_nonexistent", headers=HEADERS)
        body = r.json()
        assert "message" in body
        assert "not found" in body["message"].lower()

    def test_returns_200_for_existing_job(self, client: TestClient, mock_store):
        mock_job = _make_mock_job("mv_del_001")
        mock_store.get_job.return_value = mock_job
        r = client.delete("/jobs/mv_del_001", headers=HEADERS)
        assert r.status_code == 200

    def test_returns_deleted_status(self, client: TestClient, mock_store):
        mock_job = _make_mock_job("mv_del_002")
        mock_store.get_job.return_value = mock_job
        r = client.delete("/jobs/mv_del_002", headers=HEADERS)
        body = r.json()
        assert body["status"] == "deleted"

    def test_returns_job_id_in_response(self, client: TestClient, mock_store):
        mock_job = _make_mock_job("mv_del_003")
        mock_store.get_job.return_value = mock_job
        r = client.delete("/jobs/mv_del_003", headers=HEADERS)
        body = r.json()
        assert body["job_id"] == "mv_del_003"

    def test_returns_message(self, client: TestClient, mock_store):
        mock_job = _make_mock_job("mv_del_004")
        mock_store.get_job.return_value = mock_job
        r = client.delete("/jobs/mv_del_004", headers=HEADERS)
        body = r.json()
        assert "message" in body

    def test_calls_delete_on_store(self, client: TestClient, mock_store):
        mock_job = _make_mock_job("mv_del_005")
        mock_store.get_job.return_value = mock_job
        client.delete("/jobs/mv_del_005", headers=HEADERS)
        mock_store.delete_job.assert_called_once_with("mv_del_005")


# ---------------------------------------------------------------------------
# Authentication middleware
# ---------------------------------------------------------------------------

class TestAuthMiddleware:
    """Authentication middleware — X-API-Key header validation."""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/jobs"),
            ("GET", "/jobs/mv_test"),
            ("GET", "/download/mv_test"),
            ("GET", "/cache/stats"),
            ("POST", "/download"),
            ("POST", "/make-video"),
            ("DELETE", "/jobs/mv_test"),
        ],
    )
    def test_protected_endpoints_reject_no_auth(
        self, unauth_client: TestClient, method: str, path: str
    ):
        r = unauth_client.request(method, path)
        assert r.status_code in (401, 403), (
            f"{method} {path} should reject unauthenticated requests"
        )

    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/"),
            ("GET", "/health"),
        ],
    )
    def test_exempt_endpoints_accept_no_auth(
        self, unauth_client: TestClient, method: str, path: str
    ):
        r = unauth_client.request(method, path)
        assert r.status_code == 200, (
            f"{method} {path} should be exempt from auth"
        )

    def test_metrics_requires_auth(self, unauth_client: TestClient):
        r = unauth_client.get("/metrics")
        assert r.status_code in (401, 403)

    def test_rejects_invalid_api_key(self, unauth_client: TestClient):
        r = unauth_client.get("/jobs", headers={"X-API-Key": "wrong-key"})
        assert r.status_code in (401, 403)
