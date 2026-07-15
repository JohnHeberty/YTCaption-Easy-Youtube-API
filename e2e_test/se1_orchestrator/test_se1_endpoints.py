"""
Comprehensive E2E tests for SE1 Orchestrator service (port 8001).

Covers every endpoint with valid and invalid request scenarios.
Uses mocked Redis and overridden auth dependency to run without infrastructure.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Set env BEFORE any app import
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("APP_NAME", "se1-orchestrator")
os.environ.setdefault("VIDEO_DOWNLOADER_URL", "http://localhost:8002")
os.environ.setdefault("AUDIO_NORMALIZATION_URL", "http://localhost:8003")
os.environ.setdefault("AUDIO_TRANSCRIBER_URL", "http://localhost:8004")

import pytest
from fastapi.testclient import TestClient

from _service_loader import load_app

API_KEY = "test-api-key-2026"
HEADERS = {"X-API-Key": API_KEY}
VALID_YT_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def _make_mock_store():
    """Build a mock OrchestratorJobStore with sane defaults and in-memory job tracking."""
    jobs_db: dict[str, MagicMock] = {}
    store = MagicMock()
    store.ping.return_value = True

    def _save(job):
        jobs_db[job.id] = job
        return job

    def _get(job_id):
        return jobs_db.get(job_id)

    def _list(limit=100):
        return list(jobs_db.values())[:limit]

    def _stats():
        all_jobs = list(jobs_db.values())
        by_status: dict[str, int] = {}
        for j in all_jobs:
            s = j.status.value if hasattr(j.status, "value") else str(j.status)
            by_status[s] = by_status.get(s, 0) + 1
        return {"total_jobs": len(all_jobs), "by_status": by_status}

    def _cleanup(max_age_hours=24):
        return 0

    store.save_job.side_effect = _save
    store.get_job.side_effect = _get
    store.list_jobs.side_effect = _list
    store.get_stats.side_effect = _stats
    store.cleanup_old_jobs.side_effect = _cleanup
    store.delete_job.return_value = True
    return store


def _make_mock_orchestrator():
    """Build a mock PipelineOrchestrator."""
    orch = AsyncMock()
    orch.check_services_health.return_value = {}
    orch.video_client = MagicMock()
    orch.video_client.base_url = "http://mock-se2:8002"
    orch.audio_client = MagicMock()
    orch.audio_client.base_url = "http://mock-se3:8003"
    orch.transcription_client = MagicMock()
    orch.transcription_client.base_url = "http://mock-se4:8004"
    return orch


@pytest.fixture()
def client():
    """Create a TestClient with Redis mocked and auth bypassed."""
    app, verify_api_key = load_app("se1-orchestrator")

    mock_store = _make_mock_store()
    mock_orch = _make_mock_orchestrator()

    patches = [
        patch("app.main.get_store", return_value=mock_store),
        patch("app.main.get_pipeline_orchestrator", return_value=mock_orch),
        patch("app.main.validate_configuration", new_callable=AsyncMock),
        patch("app.main.MicroserviceClient"),
        # Patch get_store inside each route module so _get_redis_store() returns mock
        patch("app.api.health_routes.get_store", return_value=mock_store),
        patch("app.api.health_routes.get_pipeline_orchestrator", return_value=mock_orch),
        patch("app.api.admin_routes.get_store", return_value=mock_store),
        patch("app.api.admin_routes.get_pipeline_orchestrator", return_value=mock_orch),
        patch("app.api.jobs_routes.get_store", return_value=mock_store),
    ]

    for p in patches:
        p.start()

    async def _skip_auth():
        return None

    app.dependency_overrides[verify_api_key] = _skip_auth
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(verify_api_key, None)

    for p in patches:
        p.stop()


@pytest.fixture()
def unauth_client():
    """TestClient WITHOUT auth override — for testing 401/403 responses.

    Creates a fresh app via load_app() with the same mock patches as
    ``client`` but WITHOUT the auth dependency override, so requests
    hit the real auth middleware and return 401/403.

    Sets API_KEY env var so the auth dependency actually enforces key
    validation (without it, api_key is None and auth is disabled).
    """
    os.environ["API_KEY"] = API_KEY
    try:
        app, verify_api_key = load_app("se1-orchestrator")
    finally:
        os.environ.pop("API_KEY", None)

    mock_store = _make_mock_store()
    mock_orch = _make_mock_orchestrator()

    patches = [
        patch("app.main.get_store", return_value=mock_store),
        patch("app.main.get_pipeline_orchestrator", return_value=mock_orch),
        patch("app.main.validate_configuration", new_callable=AsyncMock),
        patch("app.main.MicroserviceClient"),
        patch("app.api.health_routes.get_store", return_value=mock_store),
        patch("app.api.health_routes.get_pipeline_orchestrator", return_value=mock_orch),
        patch("app.api.admin_routes.get_store", return_value=mock_store),
        patch("app.api.admin_routes.get_pipeline_orchestrator", return_value=mock_orch),
        patch("app.api.jobs_routes.get_store", return_value=mock_store),
    ]

    for p in patches:
        p.start()

    # NO auth override — this client tests unauthenticated access
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    for p in patches:
        p.stop()


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------

class TestRootEndpoint:
    """Tests for GET / (service info)."""

    def test_root_returns_200_with_service_info(self, client: TestClient):
        """GET / should return 200 with service name, version, status and endpoint map."""
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["service"] == "YouTube Caption Orchestrator"
        assert body["status"] == "running"
        assert "version" in body
        assert "endpoints" in body
        assert isinstance(body["endpoints"], dict)

    def test_root_response_matches_model(self, client: TestClient):
        """GET / response must contain all fields of RootResponse model."""
        body = client.get("/").json()
        required = {"service", "version", "status", "endpoints"}
        assert required.issubset(body.keys()), f"Missing fields: {required - body.keys()}"

    def test_root_endpoints_map_contains_expected_keys(self, client: TestClient):
        """The endpoints map should reference health, process, jobs and docs."""
        endpoints = client.get("/").json()["endpoints"]
        assert "health" in endpoints
        assert "process" in endpoints
        assert "docs" in endpoints


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self, client: TestClient):
        """GET /health should return 200 with status, service, version and timestamp."""
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["service"] == "orchestrator"
        assert body["status"] in ("healthy", "degraded", "unhealthy")
        assert "version" in body
        assert "timestamp" in body

    def test_health_contains_redis_field(self, client: TestClient):
        """GET /health must include redis_connected boolean."""
        body = client.get("/health").json()
        assert "redis_connected" in body
        assert isinstance(body["redis_connected"], bool)

    def test_health_contains_microservices_map(self, client: TestClient):
        """GET /health must include a microservices dict."""
        body = client.get("/health").json()
        assert "microservices" in body
        assert isinstance(body["microservices"], dict)

    def test_health_contains_uptime(self, client: TestClient):
        """GET /health must include uptime_seconds as a number."""
        body = client.get("/health").json()
        assert "uptime_seconds" in body
        assert isinstance(body["uptime_seconds"], (int, float))


# ---------------------------------------------------------------------------
# Process endpoint
# ---------------------------------------------------------------------------

class TestProcessEndpoint:
    """Tests for POST /process (start pipeline)."""

    def test_process_valid_url_returns_200(self, client: TestClient):
        """POST /process with a valid youtube_url should return 200 with job_id."""
        resp = client.post(
            "/process",
            json={"youtube_url": VALID_YT_URL},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert body["youtube_url"] == VALID_YT_URL
        assert body["overall_progress"] == 0.0
        assert "status" in body
        assert "message" in body

    def test_process_valid_url_returns_job_id_string(self, client: TestClient):
        """POST /process job_id must be a non-empty string."""
        body = client.post("/process", json={"youtube_url": VALID_YT_URL}).json()
        assert isinstance(body["job_id"], str)
        assert len(body["job_id"]) > 0

    def test_process_empty_body_uses_default_url(self, client: TestClient):
        """POST /process with empty body uses the default youtube_url and returns 200."""
        resp = client.post("/process", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["youtube_url"] == "https://www.youtube.com/watch?v=_xhulIrM6hw"

    def test_process_no_body_returns_422(self, client: TestClient):
        """POST /process with no JSON body at all must return 422."""
        resp = client.post("/process")
        assert resp.status_code == 422

    def test_process_invalid_url_type_returns_422(self, client: TestClient):
        """POST /process with youtube_url as integer must return 422."""
        resp = client.post("/process", json={"youtube_url": 12345})
        assert resp.status_code == 422

    def test_process_empty_string_url_accepted(self, client: TestClient):
        """POST /process with empty string youtube_url is accepted (no strict URL validation)."""
        resp = client.post("/process", json={"youtube_url": ""})
        assert resp.status_code == 200

    def test_process_with_optional_fields(self, client: TestClient):
        """POST /process with all optional fields set should still return 200."""
        resp = client.post(
            "/process",
            json={
                "youtube_url": VALID_YT_URL,
                "language": "pt",
                "language_out": "en",
                "remove_noise": False,
                "convert_to_mono": False,
                "apply_highpass_filter": True,
                "set_sample_rate_16k": False,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["youtube_url"] == VALID_YT_URL


# ---------------------------------------------------------------------------
# Jobs listing endpoint
# ---------------------------------------------------------------------------

class TestJobsEndpoint:
    """Tests for GET /jobs (list jobs)."""

    def test_list_jobs_returns_200(self, client: TestClient):
        """GET /jobs should return 200 with total and jobs list."""
        resp = client.get("/jobs", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "jobs" in body
        assert isinstance(body["jobs"], list)

    def test_list_jobs_empty_when_no_jobs(self, client: TestClient):
        """GET /jobs should return total=0 and empty jobs list on fresh instance."""
        body = client.get("/jobs", headers=HEADERS).json()
        assert body["total"] == 0
        assert body["jobs"] == []

    def test_list_jobs_with_limit_param(self, client: TestClient):
        """GET /jobs with limit=1 should accept the query parameter."""
        resp = client.get("/jobs", headers=HEADERS, params={"limit": 1})
        assert resp.status_code == 200

    def test_list_jobs_limit_too_large_rejected(self, client: TestClient):
        """GET /jobs with limit>200 must return 422 (max is 200)."""
        resp = client.get("/jobs", headers=HEADERS, params={"limit": 999})
        assert resp.status_code == 422

    def test_list_jobs_limit_zero_rejected(self, client: TestClient):
        """GET /jobs with limit=0 must return 422 (min is 1)."""
        resp = client.get("/jobs", headers=HEADERS, params={"limit": 0})
        assert resp.status_code == 422

    def test_list_jobs_requires_auth(self, unauth_client: TestClient):
        """GET /jobs without X-API-Key header must return 401 or 403."""
        resp = unauth_client.get("/jobs")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Single job status endpoint
# ---------------------------------------------------------------------------

class TestJobStatusEndpoint:
    """Tests for GET /jobs/{job_id}."""

    def test_nonexistent_job_returns_404(self, client: TestClient):
        """GET /jobs/{fake_id} should return 404 when job does not exist."""
        resp = client.get("/jobs/nonexistent_id_12345", headers=HEADERS)
        assert resp.status_code == 404

    def test_nonexistent_job_error_message(self, client: TestClient):
        """GET /jobs/{fake_id} 404 response should contain 'not found' message."""
        body = client.get("/jobs/nonexistent_id_12345", headers=HEADERS).json()
        assert "detail" in body or "message" in body or "error" in body

    def test_job_status_requires_auth(self, unauth_client: TestClient):
        """GET /jobs/{id} without auth must return 401 or 403."""
        resp = unauth_client.get("/jobs/any_id")
        assert resp.status_code in (401, 403)

    def test_job_status_after_create_returns_200(self, client: TestClient):
        """GET /jobs/{id} for a newly created job should return 200."""
        job_resp = client.post(
            "/process", json={"youtube_url": VALID_YT_URL}
        )
        job_id = job_resp.json()["job_id"]
        resp = client.get(f"/jobs/{job_id}", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == job_id
        assert body["youtube_url"] == VALID_YT_URL


# ---------------------------------------------------------------------------
# Wait for job endpoint
# ---------------------------------------------------------------------------

class TestWaitForJobEndpoint:
    """Tests for GET /jobs/{job_id}/wait."""

    def test_wait_nonexistent_job_returns_404(self, client: TestClient):
        """GET /jobs/{id}/wait for non-existent job should return 404 quickly."""
        resp = client.get(
            "/jobs/fake_wait_id_999/wait",
            headers=HEADERS,
            params={"timeout": 1},
        )
        assert resp.status_code == 404

    def test_wait_requires_auth(self, unauth_client: TestClient):
        """GET /jobs/{id}/wait without auth must return 401 or 403."""
        resp = unauth_client.get("/jobs/any_id/wait")
        assert resp.status_code in (401, 403)

    def test_wait_invalid_timeout_rejected(self, client: TestClient):
        """GET /jobs/{id}/wait with timeout=0 must return 422."""
        resp = client.get(
            "/jobs/any_id/wait",
            headers=HEADERS,
            params={"timeout": 0},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# SSE stream endpoint
# ---------------------------------------------------------------------------

class TestStreamEndpoint:
    """Tests for GET /jobs/{job_id}/stream."""

    def test_stream_nonexistent_job_returns_error_event(self, client: TestClient):
        """GET /jobs/{id}/stream for non-existent job should yield an error event then close."""
        with client.stream(
            "GET",
            "/jobs/fake_stream_id_999/stream",
            headers=HEADERS,
            params={"timeout": 1},
        ) as resp:
            assert resp.status_code == 200
            collected = b""
            for chunk in resp.iter_bytes():
                collected += chunk
            text = collected.decode("utf-8", errors="replace")
            assert "event: error" in text or "Job nao encontrado" in text

    def test_stream_returns_sse_content_type(self, client: TestClient):
        """GET /jobs/{id}/stream must return text/event-stream content type."""
        with client.stream(
            "GET",
            "/jobs/any_id/stream",
            headers=HEADERS,
            params={"timeout": 1},
        ) as resp:
            assert resp.status_code == 200
            ct = resp.headers.get("content-type", "")
            assert "text/event-stream" in ct

    def test_stream_requires_auth(self, unauth_client: TestClient):
        """GET /jobs/{id}/stream without auth must return 401 or 403."""
        resp = unauth_client.get("/jobs/any_id/stream")
        assert resp.status_code in (401, 403)

    def test_stream_invalid_timeout_rejected(self, client: TestClient):
        """GET /jobs/{id}/stream with timeout=0 must return 422."""
        resp = client.get(
            "/jobs/any_id/stream",
            headers=HEADERS,
            params={"timeout": 0},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Admin stats endpoint
# ---------------------------------------------------------------------------

class TestAdminStatsEndpoint:
    """Tests for GET /admin/stats."""

    def test_stats_returns_200(self, client: TestClient):
        """GET /admin/stats should return 200 with orchestrator, redis, settings sections."""
        resp = client.get("/admin/stats", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert "orchestrator" in body
        assert "redis" in body
        assert "settings" in body

    def test_stats_orchestrator_has_version(self, client: TestClient):
        """GET /admin/stats orchestrator section must contain version."""
        body = client.get("/admin/stats", headers=HEADERS).json()
        assert "version" in body["orchestrator"]
        assert "environment" in body["orchestrator"]

    def test_stats_settings_snapshot(self, client: TestClient):
        """GET /admin/stats settings section must contain pipeline config keys."""
        body = client.get("/admin/stats", headers=HEADERS).json()
        settings = body["settings"]
        assert "cache_ttl_hours" in settings
        assert "job_timeout_minutes" in settings

    def test_stats_requires_auth(self, unauth_client: TestClient):
        """GET /admin/stats without auth must return 401 or 403."""
        resp = unauth_client.get("/admin/stats")
        assert resp.status_code in (401, 403)

    def test_stats_redis_section_is_dict(self, client: TestClient):
        """GET /admin/stats redis section should be a dict (may be empty with mocked Redis)."""
        body = client.get("/admin/stats", headers=HEADERS).json()
        assert isinstance(body["redis"], dict)


# ---------------------------------------------------------------------------
# Admin cleanup endpoint
# ---------------------------------------------------------------------------

class TestAdminCleanupEndpoint:
    """Tests for POST /admin/cleanup."""

    def test_cleanup_returns_200(self, client: TestClient):
        """POST /admin/cleanup should return 200 with message, jobs_removed, logs_cleaned."""
        resp = client.post("/admin/cleanup", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert "message" in body
        assert "jobs_removed" in body
        assert "logs_cleaned" in body

    def test_cleanup_with_max_age_param(self, client: TestClient):
        """POST /admin/cleanup with max_age_hours should accept the query param."""
        resp = client.post(
            "/admin/cleanup",
            headers=HEADERS,
            params={"max_age_hours": 24},
        )
        assert resp.status_code == 200

    def test_cleanup_max_age_zero_rejected(self, client: TestClient):
        """POST /admin/cleanup with max_age_hours=0 must return 422 (min is 1)."""
        resp = client.post(
            "/admin/cleanup",
            headers=HEADERS,
            params={"max_age_hours": 0},
        )
        assert resp.status_code == 422

    def test_cleanup_deep_flag(self, client: TestClient):
        """POST /admin/cleanup with deep=true should still return 200."""
        resp = client.post(
            "/admin/cleanup",
            headers=HEADERS,
            params={"deep": True},
        )
        assert resp.status_code == 200

    def test_cleanup_remove_logs_flag(self, client: TestClient):
        """POST /admin/cleanup with remove_logs=true should still return 200."""
        resp = client.post(
            "/admin/cleanup",
            headers=HEADERS,
            params={"remove_logs": True},
        )
        assert resp.status_code == 200

    def test_cleanup_requires_auth(self, unauth_client: TestClient):
        """POST /admin/cleanup without auth must return 401 or 403."""
        resp = unauth_client.post("/admin/cleanup")
        assert resp.status_code in (401, 403)

    def test_cleanup_jobs_removed_is_int(self, client: TestClient):
        """POST /admin/cleanup jobs_removed must be an integer."""
        body = client.post("/admin/cleanup", headers=HEADERS).json()
        assert isinstance(body["jobs_removed"], int)


# ---------------------------------------------------------------------------
# Admin factory-reset endpoint
# ---------------------------------------------------------------------------

class TestAdminFactoryResetEndpoint:
    """Tests for POST /admin/factory-reset."""

    @patch("redis.Redis")
    @patch("httpx.AsyncClient")
    def test_factory_reset_returns_200(self, mock_httpx, mock_redis_cls, client: TestClient):
        """POST /admin/factory-reset should return 200 with orchestrator, microservices, warning."""
        mock_r = MagicMock()
        mock_r.keys.return_value = []
        mock_r.flushdb.return_value = True
        mock_redis_cls.return_value = mock_r

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": "ok"}
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_resp
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.return_value = mock_client_instance

        resp = client.post("/admin/factory-reset", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert "message" in body
        assert "orchestrator" in body
        assert "microservices" in body
        assert "warning" in body

    @patch("redis.Redis")
    @patch("httpx.AsyncClient")
    def test_factory_reset_orchestrator_section(self, mock_httpx, mock_redis_cls, client: TestClient):
        """POST /admin/factory-reset orchestrator section must have jobs_removed, redis_flushed, logs_cleaned."""
        mock_r = MagicMock()
        mock_r.keys.return_value = []
        mock_r.flushdb.return_value = True
        mock_redis_cls.return_value = mock_r

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": "ok"}
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_resp
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.return_value = mock_client_instance

        body = client.post("/admin/factory-reset", headers=HEADERS).json()
        orch = body["orchestrator"]
        assert "jobs_removed" in orch
        assert "redis_flushed" in orch
        assert "logs_cleaned" in orch
        assert isinstance(orch["jobs_removed"], int)
        assert isinstance(orch["redis_flushed"], bool)

    @patch("redis.Redis")
    @patch("httpx.AsyncClient")
    def test_factory_reset_warning_message(self, mock_httpx, mock_redis_cls, client: TestClient):
        """POST /admin/factory-reset must include a warning string about data loss."""
        mock_r = MagicMock()
        mock_r.keys.return_value = []
        mock_r.flushdb.return_value = True
        mock_redis_cls.return_value = mock_r

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": "ok"}
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_resp
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.return_value = mock_client_instance

        body = client.post("/admin/factory-reset", headers=HEADERS).json()
        assert isinstance(body["warning"], str)
        assert len(body["warning"]) > 0

    def test_factory_reset_requires_auth(self, unauth_client: TestClient):
        """POST /admin/factory-reset without auth must return 401 or 403."""
        resp = unauth_client.post("/admin/factory-reset")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Cross-cutting: auth middleware
# ---------------------------------------------------------------------------

class TestAuthMiddleware:
    """Tests verifying that auth is correctly enforced across protected endpoints."""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/jobs"),
            ("GET", "/jobs/any_id"),
            ("GET", "/jobs/any_id/wait"),
            ("GET", "/jobs/any_id/stream"),
            ("GET", "/admin/stats"),
            ("POST", "/admin/cleanup"),
            ("POST", "/admin/factory-reset"),
        ],
    )
    def test_protected_endpoints_reject_no_auth(self, unauth_client: TestClient, method, path):
        """Every protected endpoint must reject requests without an API key."""
        resp = unauth_client.request(method, path)
        assert resp.status_code in (401, 403), (
            f"{method} {path} returned {resp.status_code} without auth"
        )

    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/"),
            ("POST", "/process"),
            ("GET", "/health"),
        ],
    )
    def test_public_endpoints_accept_no_auth(self, unauth_client: TestClient, method, path):
        """Root, process, and health must be accessible without an API key."""
        if method == "POST":
            resp = unauth_client.request(method, path, json={"youtube_url": VALID_YT_URL})
        else:
            resp = unauth_client.request(method, path)
        assert resp.status_code != 401, f"{method} {path} requires auth but should be public"
        assert resp.status_code != 403, f"{method} {path} requires auth but should be public"
