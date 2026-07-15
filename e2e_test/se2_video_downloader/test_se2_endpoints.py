"""
Comprehensive E2E tests for SE2 Video Downloader service (port 8002).

Covers every endpoint with valid and invalid request scenarios.
Uses mocked Redis, mocked Celery, and overridden auth dependency
to run without any real infrastructure.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock

# Set env BEFORE any app import
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("APP_NAME", "se2-video-downloader")

import pytest
from fastapi.testclient import TestClient

from _service_loader import load_app


API_KEY = "test-api-key-2026"
HEADERS = {"X-API-Key": API_KEY}
VALID_YT_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
FAKE_JOB_ID = "vd_abc123def456"


class _NoOpRateLimitMiddleware:
    """No-op middleware that replaces RateLimiterMiddleware in tests."""

    def __init__(self, app, **kwargs):  # type: ignore[override]
        self.app = app

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


@pytest.fixture()
def client():
    """Create a TestClient with Redis, Celery, rate-limiter, and auth fully mocked."""
    mock_store = MagicMock()
    mock_store.redis = MagicMock()
    mock_store.redis.ping.return_value = True
    mock_store.redis.keys.return_value = []
    mock_store.redis.get.return_value = None
    mock_store.redis.set.return_value = True
    mock_store.get_stats.return_value = {"total_jobs": 0, "by_status": {}}
    mock_store.get_job.return_value = None
    mock_store.list_jobs.return_value = []
    mock_store.get_queue_info = AsyncMock(
        return_value={"queued": 0, "processing": 0}
    )
    mock_store.find_orphaned_jobs = AsyncMock(return_value=[])
    mock_store.start_cleanup_task = AsyncMock()
    mock_store.stop_cleanup_task = AsyncMock()

    mock_dl = MagicMock()
    mock_dl.get_user_agent_stats.return_value = {
        "total_user_agents": 3,
        "quarantined_count": 0,
        "available_count": 3,
        "error_cache_size": 0,
        "quarantine_hours": 48,
        "max_error_count": 3,
        "average_quality": 0.85,
        "quarantined_uas": [],
    }
    mock_dl.reset_user_agent.return_value = True
    mock_dl.get_file_path.return_value = None

    mock_celery_app = MagicMock()
    mock_inspect = MagicMock()
    mock_inspect.active.return_value = {"worker1": []}
    mock_celery_app.control.inspect.return_value = mock_inspect

    mock_redis_cls = MagicMock()
    mock_redis_instance = MagicMock()
    mock_redis_instance.keys.return_value = []
    mock_redis_instance.get.return_value = None
    mock_redis_instance.set.return_value = True
    mock_redis_instance.flushdb.return_value = True
    mock_redis_cls.from_url.return_value = mock_redis_instance
    mock_redis_cls.return_value = mock_redis_instance

    app, verify_api_key = load_app("se2-video-downloader")

    with (
        patch("app.main.get_job_store", return_value=mock_store),
        patch("app.main.get_downloader", return_value=mock_dl),
        patch("app.infrastructure.celery_config.celery_app", mock_celery_app),
        patch("app.infrastructure.celery_tasks.download_video_task"),
        patch("redis.Redis", mock_redis_cls),
        patch("common.middleware.RateLimiterMiddleware", _NoOpRateLimitMiddleware),
    ):
        from app.infrastructure.dependencies import job_store, downloader

        job_store.set(mock_store)
        downloader.set(mock_dl)

        async def _skip_auth():
            return None

        app.dependency_overrides[verify_api_key] = _skip_auth

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        job_store.reset()
        downloader.reset()
        app.dependency_overrides.pop(verify_api_key, None)


@pytest.fixture()
def unauth_client():
    """TestClient WITHOUT auth override — for testing 401 responses.

    Creates a fresh app via load_app() with the same mock patches as
    ``client`` but WITHOUT the auth dependency override, so requests
    hit the real auth middleware and return 401.
    """
    mock_store = MagicMock()
    mock_store.redis = MagicMock()
    mock_store.redis.ping.return_value = True
    mock_store.redis.keys.return_value = []
    mock_store.redis.get.return_value = None
    mock_store.redis.set.return_value = True
    mock_store.get_stats.return_value = {"total_jobs": 0, "by_status": {}}
    mock_store.get_job.return_value = None
    mock_store.list_jobs.return_value = []
    mock_store.get_queue_info = AsyncMock(
        return_value={"queued": 0, "processing": 0}
    )
    mock_store.find_orphaned_jobs = AsyncMock(return_value=[])
    mock_store.start_cleanup_task = AsyncMock()
    mock_store.stop_cleanup_task = AsyncMock()

    mock_dl = MagicMock()
    mock_dl.get_user_agent_stats.return_value = {
        "total_user_agents": 3,
        "quarantined_count": 0,
        "available_count": 3,
        "error_cache_size": 0,
        "quarantine_hours": 48,
        "max_error_count": 3,
        "average_quality": 0.85,
        "quarantined_uas": [],
    }
    mock_dl.reset_user_agent.return_value = True
    mock_dl.get_file_path.return_value = None

    mock_celery_app = MagicMock()
    mock_inspect = MagicMock()
    mock_inspect.active.return_value = {"worker1": []}
    mock_celery_app.control.inspect.return_value = mock_inspect

    mock_redis_cls = MagicMock()
    mock_redis_instance = MagicMock()
    mock_redis_instance.keys.return_value = []
    mock_redis_instance.get.return_value = None
    mock_redis_instance.set.return_value = True
    mock_redis_instance.flushdb.return_value = True
    mock_redis_cls.from_url.return_value = mock_redis_instance
    mock_redis_cls.return_value = mock_redis_instance

    os.environ["API_KEY"] = API_KEY
    try:
        app, verify_api_key = load_app("se2-video-downloader")
    finally:
        os.environ.pop("API_KEY", None)

    with (
        patch("app.main.get_job_store", return_value=mock_store),
        patch("app.main.get_downloader", return_value=mock_dl),
        patch("app.infrastructure.celery_config.celery_app", mock_celery_app),
        patch("app.infrastructure.celery_tasks.download_video_task"),
        patch("redis.Redis", mock_redis_cls),
        patch("common.middleware.RateLimiterMiddleware", _NoOpRateLimitMiddleware),
    ):
        from app.infrastructure.dependencies import job_store, downloader

        job_store.set(mock_store)
        downloader.set(mock_dl)

        # NO auth override — this client tests unauthenticated access
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        job_store.reset()
        downloader.reset()


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------


class TestRootEndpoint:
    """Tests for GET / (service info)."""

    def test_root_returns_200(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_contains_service_name(self, client: TestClient):
        body = client.get("/").json()
        assert body["service"] == "Video Downloader Service"

    def test_root_contains_version(self, client: TestClient):
        body = client.get("/").json()
        assert body["version"] == "3.0.0"

    def test_root_contains_status_running(self, client: TestClient):
        body = client.get("/").json()
        assert body["status"] == "running"

    def test_root_contains_endpoints_map(self, client: TestClient):
        body = client.get("/").json()
        assert "endpoints" in body
        endpoints = body["endpoints"]
        assert "health" in endpoints
        assert "jobs" in endpoints
        assert "admin" in endpoints
        assert "user_agents" in endpoints

    def test_root_endpoints_jobs_has_expected_keys(self, client: TestClient):
        jobs = client.get("/").json()["endpoints"]["jobs"]
        assert "create" in jobs
        assert "get" in jobs
        assert "list" in jobs
        assert "download" in jobs
        assert "delete" in jobs
        assert "orphaned" in jobs

    def test_root_endpoints_admin_has_expected_keys(self, client: TestClient):
        admin = client.get("/").json()["endpoints"]["admin"]
        assert "stats" in admin
        assert "queue" in admin
        assert "cleanup" in admin

    def test_root_endpoints_user_agents_has_expected_keys(self, client: TestClient):
        ua = client.get("/").json()["endpoints"]["user_agents"]
        assert "stats" in ua
        assert "reset" in ua

    def test_root_contains_description(self, client: TestClient):
        body = client.get("/").json()
        assert "description" in body
        assert len(body["description"]) > 0


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_contains_status(self, client: TestClient):
        body = client.get("/health").json()
        assert body["status"] in ("healthy", "degraded", "unhealthy")

    def test_health_contains_service_name(self, client: TestClient):
        body = client.get("/health").json()
        assert body["service"] == "video-downloader"

    def test_health_contains_version(self, client: TestClient):
        body = client.get("/health").json()
        assert "version" in body

    def test_health_contains_timestamp(self, client: TestClient):
        body = client.get("/health").json()
        assert "timestamp" in body

    def test_health_contains_checks(self, client: TestClient):
        body = client.get("/health").json()
        assert "checks" in body
        assert isinstance(body["checks"], dict)

    def test_health_checks_include_redis(self, client: TestClient):
        body = client.get("/health").json()
        assert "redis" in body["checks"]

    def test_health_checks_include_celery(self, client: TestClient):
        body = client.get("/health").json()
        assert "celery_worker" in body["checks"]


# ---------------------------------------------------------------------------
# Metrics endpoint
# ---------------------------------------------------------------------------


class TestMetricsEndpoint:
    """Tests for GET /metrics."""

    def test_metrics_returns_200(self, client: TestClient):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_returns_text_plain(self, client: TestClient):
        resp = client.get("/metrics")
        assert "text/plain" in resp.headers["content-type"]

    def test_metrics_contains_prometheus_help(self, client: TestClient):
        text = client.get("/metrics").text
        assert "# HELP" in text

    def test_metrics_contains_prometheus_type(self, client: TestClient):
        text = client.get("/metrics").text
        assert "# TYPE" in text

    def test_metrics_contains_jobs_store_total(self, client: TestClient):
        text = client.get("/metrics").text
        assert "video_downloader_jobs_store_total" in text

    def test_metrics_ends_with_newline(self, client: TestClient):
        text = client.get("/metrics").text
        assert text.endswith("\n")


# ---------------------------------------------------------------------------
# User-Agent stats endpoint
# ---------------------------------------------------------------------------


class TestUserAgentStatsEndpoint:
    """Tests for GET /user-agents/stats."""

    def test_stats_returns_200(self, client: TestClient):
        resp = client.get("/user-agents/stats")
        assert resp.status_code == 200

    def test_stats_contains_total_user_agents(self, client: TestClient):
        body = client.get("/user-agents/stats").json()
        assert "total_user_agents" in body
        assert isinstance(body["total_user_agents"], int)

    def test_stats_contains_quarantined_count(self, client: TestClient):
        body = client.get("/user-agents/stats").json()
        assert "quarantined_count" in body
        assert isinstance(body["quarantined_count"], int)

    def test_stats_contains_available_count(self, client: TestClient):
        body = client.get("/user-agents/stats").json()
        assert "available_count" in body
        assert isinstance(body["available_count"], int)

    def test_stats_contains_quality_fields(self, client: TestClient):
        body = client.get("/user-agents/stats").json()
        assert "average_quality" in body
        assert "quarantine_hours" in body
        assert "max_error_count" in body

    def test_stats_contains_quarantined_uas_list(self, client: TestClient):
        body = client.get("/user-agents/stats").json()
        assert "quarantined_uas" in body
        assert isinstance(body["quarantined_uas"], list)


# ---------------------------------------------------------------------------
# User-Agent reset endpoint
# ---------------------------------------------------------------------------


class TestUserAgentResetEndpoint:
    """Tests for POST /user-agents/reset/{user_agent_id}."""

    def test_reset_returns_200(self, client: TestClient):
        resp = client.post("/user-agents/reset/test-ua-id")
        assert resp.status_code == 200

    def test_reset_contains_success_field(self, client: TestClient):
        body = client.post("/user-agents/reset/test-ua-id").json()
        assert "success" in body
        assert isinstance(body["success"], bool)

    def test_reset_contains_user_agent_field(self, client: TestClient):
        body = client.post("/user-agents/reset/test-ua-id").json()
        assert "user_agent" in body

    def test_reset_contains_message_field(self, client: TestClient):
        body = client.post("/user-agents/reset/test-ua-id").json()
        assert "message" in body

    def test_reset_with_long_id_truncates(self, client: TestClient):
        long_id = "a" * 100
        body = client.post(f"/user-agents/reset/{long_id}").json()
        assert body["user_agent"].endswith("...")

    def test_reset_with_short_id_not_truncated(self, client: TestClient):
        short_id = "short-id"
        body = client.post(f"/user-agents/reset/{short_id}").json()
        assert not body["user_agent"].endswith("...")


# ---------------------------------------------------------------------------
# POST /jobs (create download job)
# ---------------------------------------------------------------------------


class TestCreateJobEndpoint:
    """Tests for POST /jobs."""

    def test_create_job_200_valid_url(self, client: TestClient):
        resp = client.post(
            "/jobs",
            json={"url": VALID_YT_URL},
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_create_job_200_with_quality(self, client: TestClient):
        resp = client.post(
            "/jobs",
            json={"url": VALID_YT_URL, "quality": "720p"},
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_create_job_200_audio_quality(self, client: TestClient):
        resp = client.post(
            "/jobs",
            json={"url": VALID_YT_URL, "quality": "audio"},
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_create_job_response_has_id(self, client: TestClient):
        body = client.post(
            "/jobs", json={"url": VALID_YT_URL}, headers=HEADERS
        ).json()
        assert "id" in body
        assert body["id"].startswith("vd_")

    def test_create_job_response_has_status(self, client: TestClient):
        body = client.post(
            "/jobs", json={"url": VALID_YT_URL}, headers=HEADERS
        ).json()
        assert "status" in body
        assert body["status"] in ("queued", "processing", "completed")

    def test_create_job_response_has_url(self, client: TestClient):
        body = client.post(
            "/jobs", json={"url": VALID_YT_URL}, headers=HEADERS
        ).json()
        assert body["url"] == VALID_YT_URL

    def test_create_job_response_has_quality(self, client: TestClient):
        body = client.post(
            "/jobs", json={"url": VALID_YT_URL}, headers=HEADERS
        ).json()
        assert "quality" in body

    def test_create_job_response_has_progress(self, client: TestClient):
        body = client.post(
            "/jobs", json={"url": VALID_YT_URL}, headers=HEADERS
        ).json()
        assert "progress" in body
        assert isinstance(body["progress"], (int, float))

    def test_create_job_response_has_created_at(self, client: TestClient):
        body = client.post(
            "/jobs", json={"url": VALID_YT_URL}, headers=HEADERS
        ).json()
        assert "created_at" in body

    def test_create_job_response_has_expires_at(self, client: TestClient):
        body = client.post(
            "/jobs", json={"url": VALID_YT_URL}, headers=HEADERS
        ).json()
        assert "expires_at" in body

    def test_create_job_422_missing_url(self, client: TestClient):
        resp = client.post("/jobs", json={}, headers=HEADERS)
        assert resp.status_code == 422

    def test_create_job_422_empty_body(self, client: TestClient):
        resp = client.post(
            "/jobs",
            content=b"",
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_create_job_500_invalid_quality(self, client: TestClient):
        """Invalid quality raises ValueError in field_validator.

        The ValueError propagates into the shared validation exception
        handler which fails to JSON-serialize it, resulting in 500.
        This documents the actual behaviour of the service.
        """
        resp = client.post(
            "/jobs",
            json={"url": VALID_YT_URL, "quality": "ultra_hd_8k"},
            headers=HEADERS,
        )
        assert resp.status_code == 500

    def test_create_job_422_url_too_short(self, client: TestClient):
        resp = client.post(
            "/jobs", json={"url": "abc"}, headers=HEADERS
        )
        assert resp.status_code == 422

    def test_create_job_500_store_error(self, client: TestClient):
        from app.infrastructure.dependencies import job_store

        mock_store = MagicMock()
        mock_store.redis = MagicMock()
        mock_store.save_job.side_effect = RuntimeError("Redis down")
        job_store.set(mock_store)
        try:
            resp = client.post(
                "/jobs", json={"url": VALID_YT_URL}, headers=HEADERS
            )
            assert resp.status_code == 500
        finally:
            job_store.reset()


# ---------------------------------------------------------------------------
# GET /jobs (list jobs)
# ---------------------------------------------------------------------------


class TestListJobsEndpoint:
    """Tests for GET /jobs."""

    def test_list_jobs_200_empty(self, client: TestClient):
        resp = client.get("/jobs", headers=HEADERS)
        assert resp.status_code == 200

    def test_list_jobs_returns_list(self, client: TestClient):
        body = client.get("/jobs", headers=HEADERS).json()
        assert isinstance(body, list)

    def test_list_jobs_empty_by_default(self, client: TestClient):
        body = client.get("/jobs", headers=HEADERS).json()
        assert len(body) == 0

    def test_list_jobs_with_limit_param(self, client: TestClient):
        resp = client.get("/jobs?limit=5", headers=HEADERS)
        assert resp.status_code == 200

    def test_list_jobs_422_limit_zero(self, client: TestClient):
        resp = client.get("/jobs?limit=0", headers=HEADERS)
        assert resp.status_code == 422

    def test_list_jobs_422_limit_too_high(self, client: TestClient):
        resp = client.get("/jobs?limit=999", headers=HEADERS)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}
# ---------------------------------------------------------------------------


class TestGetJobEndpoint:
    """Tests for GET /jobs/{job_id}."""

    def test_get_job_404_nonexistent(self, client: TestClient):
        resp = client.get(f"/jobs/{FAKE_JOB_ID}", headers=HEADERS)
        assert resp.status_code == 404

    def test_get_job_404_response_has_message(self, client: TestClient):
        body = client.get(f"/jobs/{FAKE_JOB_ID}", headers=HEADERS).json()
        assert "message" in body

    def test_get_job_404_message_is_job_not_found(self, client: TestClient):
        body = client.get(f"/jobs/{FAKE_JOB_ID}", headers=HEADERS).json()
        assert body["message"] == "Job not found"


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/download
# ---------------------------------------------------------------------------


class TestDownloadJobEndpoint:
    """Tests for GET /jobs/{job_id}/download."""

    def test_download_job_404_nonexistent(self, client: TestClient):
        resp = client.get(
            f"/jobs/{FAKE_JOB_ID}/download", headers=HEADERS
        )
        assert resp.status_code == 404

    def test_download_job_404_response_has_message(self, client: TestClient):
        body = client.get(
            f"/jobs/{FAKE_JOB_ID}/download", headers=HEADERS
        ).json()
        assert "message" in body

    def test_download_job_425_not_ready(self, client: TestClient):
        from app.infrastructure.dependencies import job_store
        from app.core.models import VideoDownloadJob

        incomplete_job = VideoDownloadJob(
            id=FAKE_JOB_ID,
            url=VALID_YT_URL,
            status="queued",
        )
        mock_store = MagicMock()
        mock_store.redis = MagicMock()
        mock_store.get_job.return_value = incomplete_job
        job_store.set(mock_store)
        try:
            resp = client.get(
                f"/jobs/{FAKE_JOB_ID}/download", headers=HEADERS
            )
            assert resp.status_code == 425
        finally:
            job_store.reset()


# ---------------------------------------------------------------------------
# DELETE /jobs/{job_id}
# ---------------------------------------------------------------------------


class TestDeleteJobEndpoint:
    """Tests for DELETE /jobs/{job_id}."""

    def test_delete_job_404_nonexistent(self, client: TestClient):
        resp = client.delete(f"/jobs/{FAKE_JOB_ID}", headers=HEADERS)
        assert resp.status_code == 404

    def test_delete_job_404_response_has_message(self, client: TestClient):
        body = client.delete(f"/jobs/{FAKE_JOB_ID}", headers=HEADERS).json()
        assert "message" in body

    def test_delete_job_200_existing(self, client: TestClient):
        from app.infrastructure.dependencies import job_store
        from app.core.models import VideoDownloadJob

        existing_job = VideoDownloadJob(
            id=FAKE_JOB_ID,
            url=VALID_YT_URL,
            status="completed",
            file_path="/tmp/test.mp4",
        )
        mock_store = MagicMock()
        mock_store.redis = MagicMock()
        mock_store.get_job.return_value = existing_job
        job_store.set(mock_store)
        try:
            resp = client.delete(f"/jobs/{FAKE_JOB_ID}", headers=HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            assert body["job_id"] == FAKE_JOB_ID
            assert body["message"] == "Job deleted successfully"
            assert "files_deleted" in body
        finally:
            job_store.reset()


# ---------------------------------------------------------------------------
# GET /jobs/orphaned
#
# NOTE: Route ordering bug — GET /jobs/{job_id} is registered before
# GET /jobs/orphaned in jobs_routes.py, so FastAPI matches "orphaned"
# as a {job_id} path parameter.  The endpoint therefore returns 404
# instead of 200 in production.  Tests below document the ACTUAL
# behaviour of the service as-is.
# ---------------------------------------------------------------------------


class TestOrphanedJobsEndpoint:
    """Tests for GET /jobs/orphaned.

    Due to a route ordering bug, this endpoint is shadowed by
    GET /jobs/{job_id} and always returns 404.
    """

    def test_orphaned_jobs_shadowed_by_get_job(self, client: TestClient):
        """GET /jobs/orphaned is matched by /jobs/{job_id} → 404."""
        resp = client.get("/jobs/orphaned", headers=HEADERS)
        assert resp.status_code == 404

    def test_orphaned_jobs_404_response_format(self, client: TestClient):
        body = client.get("/jobs/orphaned", headers=HEADERS).json()
        assert "message" in body


# ---------------------------------------------------------------------------
# POST /jobs/orphaned/cleanup
# ---------------------------------------------------------------------------


class TestOrphanedCleanupEndpoint:
    """Tests for POST /jobs/orphaned/cleanup."""

    def test_orphaned_cleanup_200_no_orphans(self, client: TestClient):
        resp = client.post("/jobs/orphaned/cleanup", headers=HEADERS)
        assert resp.status_code == 200

    def test_orphaned_cleanup_response_has_status(self, client: TestClient):
        body = client.post("/jobs/orphaned/cleanup", headers=HEADERS).json()
        assert body["status"] == "success"

    def test_orphaned_cleanup_response_has_count(self, client: TestClient):
        body = client.post("/jobs/orphaned/cleanup", headers=HEADERS).json()
        assert "count" in body
        assert body["count"] == 0

    def test_orphaned_cleanup_response_has_message(self, client: TestClient):
        body = client.post("/jobs/orphaned/cleanup", headers=HEADERS).json()
        assert "message" in body

    def test_orphaned_cleanup_with_mark_as_failed_false(self, client: TestClient):
        resp = client.post(
            "/jobs/orphaned/cleanup?mark_as_failed=false", headers=HEADERS
        )
        assert resp.status_code == 200

    def test_orphaned_cleanup_with_custom_max_age(self, client: TestClient):
        resp = client.post(
            "/jobs/orphaned/cleanup?max_age_minutes=60", headers=HEADERS
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /admin/stats
# ---------------------------------------------------------------------------


class TestAdminStatsEndpoint:
    """Tests for GET /admin/stats."""

    def test_admin_stats_200(self, client: TestClient):
        resp = client.get("/admin/stats", headers=HEADERS)
        assert resp.status_code == 200

    def test_admin_stats_has_total_jobs(self, client: TestClient):
        body = client.get("/admin/stats", headers=HEADERS).json()
        assert "total_jobs" in body
        assert isinstance(body["total_jobs"], int)

    def test_admin_stats_has_by_status(self, client: TestClient):
        body = client.get("/admin/stats", headers=HEADERS).json()
        assert "by_status" in body
        assert isinstance(body["by_status"], dict)

    def test_admin_stats_has_cache_info(self, client: TestClient):
        body = client.get("/admin/stats", headers=HEADERS).json()
        assert "cache" in body

    def test_admin_stats_has_celery_info(self, client: TestClient):
        body = client.get("/admin/stats", headers=HEADERS).json()
        assert "celery" in body


# ---------------------------------------------------------------------------
# GET /admin/queue
# ---------------------------------------------------------------------------


class TestAdminQueueEndpoint:
    """Tests for GET /admin/queue."""

    def test_admin_queue_200(self, client: TestClient):
        resp = client.get("/admin/queue", headers=HEADERS)
        assert resp.status_code == 200

    def test_admin_queue_has_status(self, client: TestClient):
        body = client.get("/admin/queue", headers=HEADERS).json()
        assert body["status"] == "success"

    def test_admin_queue_has_queue_info(self, client: TestClient):
        body = client.get("/admin/queue", headers=HEADERS).json()
        assert "queue" in body


# ---------------------------------------------------------------------------
# POST /admin/cleanup
# ---------------------------------------------------------------------------


class TestAdminCleanupEndpoint:
    """Tests for POST /admin/cleanup."""

    def test_admin_cleanup_200_basic(self, client: TestClient):
        resp = client.post("/admin/cleanup", headers=HEADERS)
        assert resp.status_code == 200

    def test_admin_cleanup_200_deep(self, client: TestClient):
        resp = client.post("/admin/cleanup?deep=true", headers=HEADERS)
        assert resp.status_code == 200

    def test_admin_cleanup_basic_has_jobs_removed(self, client: TestClient):
        body = client.post("/admin/cleanup", headers=HEADERS).json()
        assert "jobs_removed" in body

    def test_admin_cleanup_basic_has_files_deleted(self, client: TestClient):
        body = client.post("/admin/cleanup", headers=HEADERS).json()
        assert "files_deleted" in body

    def test_admin_cleanup_basic_has_space_freed(self, client: TestClient):
        body = client.post("/admin/cleanup", headers=HEADERS).json()
        assert "space_freed_mb" in body

    def test_admin_cleanup_basic_has_errors_list(self, client: TestClient):
        body = client.post("/admin/cleanup", headers=HEADERS).json()
        assert "errors" in body
        assert isinstance(body["errors"], list)

    def test_admin_cleanup_deep_has_redis_flushed(self, client: TestClient):
        body = client.post("/admin/cleanup?deep=true", headers=HEADERS).json()
        assert "redis_flushed" in body

    def test_admin_cleanup_with_purge_celery(self, client: TestClient):
        resp = client.post(
            "/admin/cleanup?deep=true&purge_celery_queue=true",
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_admin_cleanup_has_message(self, client: TestClient):
        body = client.post("/admin/cleanup", headers=HEADERS).json()
        assert "message" in body


# ---------------------------------------------------------------------------
# POST /admin/fix-stuck-jobs
# ---------------------------------------------------------------------------


class TestAdminFixStuckJobsEndpoint:
    """Tests for POST /admin/fix-stuck-jobs."""

    def test_fix_stuck_jobs_200(self, client: TestClient):
        resp = client.post("/admin/fix-stuck-jobs", headers=HEADERS)
        assert resp.status_code == 200

    def test_fix_stuck_jobs_has_fixed_count(self, client: TestClient):
        body = client.post("/admin/fix-stuck-jobs", headers=HEADERS).json()
        assert "fixed_count" in body
        assert isinstance(body["fixed_count"], int)

    def test_fix_stuck_jobs_has_max_age(self, client: TestClient):
        body = client.post("/admin/fix-stuck-jobs", headers=HEADERS).json()
        assert "max_age_minutes" in body

    def test_fix_stuck_jobs_has_message(self, client: TestClient):
        body = client.post("/admin/fix-stuck-jobs", headers=HEADERS).json()
        assert "message" in body

    def test_fix_stuck_jobs_zero_when_no_stuck(self, client: TestClient):
        body = client.post("/admin/fix-stuck-jobs", headers=HEADERS).json()
        assert body["fixed_count"] == 0

    def test_fix_stuck_jobs_with_custom_max_age(self, client: TestClient):
        resp = client.post(
            "/admin/fix-stuck-jobs?max_age_minutes=60", headers=HEADERS
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["max_age_minutes"] == 60

    def test_fix_stuck_jobs_422_invalid_max_age(self, client: TestClient):
        resp = client.post(
            "/admin/fix-stuck-jobs?max_age_minutes=0", headers=HEADERS
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------


class TestAuthEnforcement:
    """Tests verifying that protected endpoints require X-API-Key."""

    PROTECTED_ENDPOINTS = [
        ("GET", "/jobs"),
        ("POST", "/jobs"),
        ("GET", f"/jobs/{FAKE_JOB_ID}"),
        ("GET", f"/jobs/{FAKE_JOB_ID}/download"),
        ("DELETE", f"/jobs/{FAKE_JOB_ID}"),
        ("POST", "/jobs/orphaned/cleanup"),
        ("GET", "/admin/stats"),
        ("GET", "/admin/queue"),
        ("POST", "/admin/cleanup"),
        ("POST", "/admin/fix-stuck-jobs"),
        ("GET", "/user-agents/stats"),
        ("POST", "/user-agents/reset/test-id"),
    ]

    def test_all_protected_endpoints_require_auth(self, unauth_client: TestClient):
        for method, path in self.PROTECTED_ENDPOINTS:
            if method == "GET":
                resp = unauth_client.get(path)
            elif method == "POST":
                resp = unauth_client.post(path, json={})
            elif method == "DELETE":
                resp = unauth_client.delete(path)
            else:
                continue
            assert resp.status_code == 401, (
                f"{method} {path} should return 401 without API key, "
                f"got {resp.status_code}"
            )

    def test_root_and_health_exempt_from_auth(self, unauth_client: TestClient):
        """GET / and GET /health should work without API key."""
        assert unauth_client.get("/").status_code == 200
        assert unauth_client.get("/health").status_code == 200
