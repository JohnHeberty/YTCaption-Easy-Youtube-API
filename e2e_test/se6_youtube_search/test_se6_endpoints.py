"""E2E tests for SE6 YouTube Search service — ALL public endpoints."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from _service_loader import load_app

API_KEY = "test-api-key-2026"

os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_KEY", API_KEY)
HEADERS = {"X-API-Key": API_KEY}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_job(
    job_id: str = "ys_abc123def456",
    status: Any = None,
    search_type: Any = None,
    **extra: Any,
) -> MagicMock:
    """Create a mock Job with all fields used by SE6 routes.

    Uses real enum values where the code does equality checks (e.g.
    ``job.status != JobStatus.COMPLETED``).
    """
    from app.domain.models import JobStatus, SearchType

    if status is None:
        status = JobStatus.COMPLETED
    elif isinstance(status, str):
        status = JobStatus(status)

    if search_type is None:
        search_type = SearchType.VIDEO
    elif isinstance(search_type, str):
        search_type = SearchType(search_type)

    job = MagicMock()
    job.id = job_id
    job.status = status
    job.search_type = search_type
    job.query = extra.get("query", "python tutorial")
    job.video_id = extra.get("video_id", "dQw4w9WgXcQ")
    job.channel_id = extra.get("channel_id", "UCuAXFkgsw1L7xaCfnd5JJOw")
    job.playlist_id = extra.get("playlist_id", "PLrAXtmRdnEQy6nuqo2XWY5vY3w8VYl2AB")
    job.max_results = extra.get("max_results", 10)
    job.include_videos = extra.get("include_videos", False)
    job.result = extra.get("result", {"videos": [{"id": "test", "title": "Test Video"}]})
    job.progress = extra.get("progress", 100.0)
    job.error_message = extra.get("error_message", None)
    job.is_expired = extra.get("is_expired", False)
    job.received_at = extra.get(
        "received_at",
        datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    job.created_at = extra.get(
        "created_at",
        datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    job.started_at = extra.get(
        "started_at",
        datetime(2026, 1, 1, 12, 0, 1, tzinfo=timezone.utc),
    )
    job.completed_at = extra.get(
        "completed_at",
        datetime(2026, 1, 1, 12, 0, 10, tzinfo=timezone.utc),
    )
    job.expires_at = extra.get(
        "expires_at",
        datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc),
    )
    job.stages = extra.get("stages", [])

    job.model_dump.return_value = {
        "id": job_id,
        "status": status.value if hasattr(status, "value") else str(status),
        "search_type": search_type.value if hasattr(search_type, "value") else str(search_type),
        "query": job.query,
        "video_id": job.video_id,
        "channel_id": job.channel_id,
        "playlist_id": job.playlist_id,
        "max_results": job.max_results,
        "include_videos": job.include_videos,
        "result": job.result,
        "progress": job.progress,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if hasattr(job.created_at, "isoformat") else str(job.created_at),
    }
    return job


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_job_store() -> MagicMock:
    """Mock YouTubeSearchJobStore with sensible defaults.

    ``get_job`` defaults to ``None`` so search endpoints create fresh jobs.
    Tests that need an existing job override it explicitly.
    """
    store = MagicMock()
    store.redis = MagicMock()
    store.get_job.return_value = None
    store.list_jobs.return_value = []
    store.delete_job.return_value = True
    store.find_orphaned_jobs = AsyncMock(return_value=[])
    store.get_queue_info = AsyncMock(return_value={"celery": "ok"})
    store.get_stats.return_value = {
        "total_jobs": 1,
        "by_status": {"completed": 1},
    }
    store.start_cleanup_task = AsyncMock()
    store.stop_cleanup_task = AsyncMock()
    store.update_job = MagicMock()
    store.save_job = MagicMock()
    store.cleanup_expired = MagicMock(return_value=0)
    return store


@pytest.fixture
def mock_celery_task() -> MagicMock:
    """Mock the Celery YouTube search task."""
    mock_task = MagicMock()
    mock_task.apply_async = MagicMock(return_value=MagicMock(id="celery-task-001"))
    return mock_task


def _make_celery_inspect_mock() -> MagicMock:
    """Return a mock ``celery_app.control.inspect()`` that yields empty results."""
    inspect_mock = MagicMock()
    inspect_mock.active.return_value = {}
    inspect_mock.registered.return_value = []
    inspect_mock.scheduled.return_value = {}
    inspect_mock.active_queues.return_value = []
    return inspect_mock


@pytest.fixture
def client(mock_job_store: MagicMock, mock_celery_task: MagicMock):
    """Yield a TestClient with all SE6 dependencies mocked."""
    mock_inspect = _make_celery_inspect_mock()

    with patch(
        "common.redis_utils.resilient_store.ResilientRedisStore._test_connection"
    ):
        app, verify_api_key = load_app("se6-youtube-search")
        from app.infrastructure.dependencies import job_store

        async def _skip_auth() -> None:
            return None

        app.dependency_overrides[verify_api_key] = _skip_auth
        job_store.set(mock_job_store)

        with patch(
            "app.api.search.youtube_search_task",
            mock_celery_task,
        ), patch(
            "app.api.admin.celery_app.control",
        ) as mock_control:
            mock_control.inspect.return_value = mock_inspect
            with TestClient(app, raise_server_exceptions=False) as c:
                yield c

        app.dependency_overrides.pop(verify_api_key, None)
        job_store.reset()


# ---------------------------------------------------------------------------
# GET /  (Root)
# ---------------------------------------------------------------------------


class TestRoot:
    def test_get_root_returns_200(self, client: TestClient):
        r = client.get("/", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["service"] == "YouTube Search Service"
        assert body["version"] == "1.0.0"
        assert body["status"] == "running"
        assert "endpoints" in body

    def test_root_endpoints_catalog(self, client: TestClient):
        r = client.get("/", headers=HEADERS)
        body = r.json()
        endpoints = body["endpoints"]
        assert "search_video_info" in endpoints
        assert "search_channel_info" in endpoints
        assert "search_playlist_info" in endpoints
        assert "search_videos" in endpoints
        assert "search_shorts" in endpoints
        assert "search_related_videos" in endpoints
        assert "get_job" in endpoints
        assert "admin_stats" in endpoints


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_structure(self, client: TestClient):
        r = client.get("/health", headers=HEADERS)
        body = r.json()
        assert "status" in body
        assert "service" in body
        assert "checks" in body

    def test_health_checks_keys(self, client: TestClient):
        r = client.get("/health", headers=HEADERS)
        body = r.json()
        checks = body["checks"]
        assert "redis" in checks
        assert "celery_workers" in checks
        assert "disk_space" in checks

    def test_health_disk_space_ok(self, client: TestClient):
        r = client.get("/health", headers=HEADERS)
        body = r.json()
        disk = body["checks"]["disk_space"]
        assert disk["status"] == "ok"
        assert disk["free_gb"] > 0
        assert disk["percent_free"] > 0


# ---------------------------------------------------------------------------
# POST /search/video-info
# ---------------------------------------------------------------------------


class TestSearchVideoInfo:
    def test_video_info_valid_returns_200(
        self, client: TestClient,
    ):
        r = client.post("/search/video-info?video_id=dQw4w9WgXcQ", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "id" in body
        assert body["search_type"] == "video_info"
        assert body["video_id"] == "dQw4w9WgXcQ"

    def test_video_info_with_url(self, client: TestClient):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        r = client.post(f"/search/video-info?video_id={url}", headers=HEADERS)
        assert r.status_code == 200

    def test_video_info_missing_param_returns_422(self, client: TestClient):
        r = client.post("/search/video-info", headers=HEADERS)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /search/channel-info
# ---------------------------------------------------------------------------


class TestSearchChannelInfo:
    def test_channel_info_valid_returns_200(self, client: TestClient):
        r = client.post(
            "/search/channel-info?channel_id=UCuAXFkgsw1L7xaCfnd5JJOw",
            headers=HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["search_type"] == "channel_info"
        assert body["channel_id"] == "UCuAXFkgsw1L7xaCfnd5JJOw"

    def test_channel_info_with_include_videos(self, client: TestClient):
        r = client.post(
            "/search/channel-info?channel_id=UCuAXFkgsw1L7xaCfnd5JJOw&include_videos=true",
            headers=HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["include_videos"] is True

    def test_channel_info_missing_param_returns_422(self, client: TestClient):
        r = client.post("/search/channel-info", headers=HEADERS)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /search/playlist-info
# ---------------------------------------------------------------------------


class TestSearchPlaylistInfo:
    def test_playlist_info_valid_returns_200(self, client: TestClient):
        r = client.post(
            "/search/playlist-info?playlist_id=PLrAXtmRdnEQy6nuqo2XWY5vY3w8VYl2AB",
            headers=HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["search_type"] == "playlist_info"
        assert body["playlist_id"] == "PLrAXtmRdnEQy6nuqo2XWY5vY3w8VYl2AB"

    def test_playlist_info_missing_param_returns_422(self, client: TestClient):
        r = client.post("/search/playlist-info", headers=HEADERS)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /search/videos
# ---------------------------------------------------------------------------


class TestSearchVideos:
    def test_videos_valid_returns_200(self, client: TestClient):
        r = client.post("/search/videos?query=python+tutorial", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["search_type"] == "video"
        assert body["query"] == "python tutorial"

    def test_videos_with_max_results(self, client: TestClient):
        r = client.post(
            "/search/videos?query=python+tutorial&max_results=25",
            headers=HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["max_results"] == 25

    def test_videos_max_results_boundary_50(self, client: TestClient):
        r = client.post(
            "/search/videos?query=test&max_results=50",
            headers=HEADERS,
        )
        assert r.status_code == 200

    def test_videos_max_results_too_high_returns_422(self, client: TestClient):
        r = client.post(
            "/search/videos?query=test&max_results=51",
            headers=HEADERS,
        )
        assert r.status_code == 422

    def test_videos_max_results_zero_returns_422(self, client: TestClient):
        r = client.post(
            "/search/videos?query=test&max_results=0",
            headers=HEADERS,
        )
        assert r.status_code == 422

    def test_videos_missing_query_returns_422(self, client: TestClient):
        r = client.post("/search/videos", headers=HEADERS)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /search/shorts
# ---------------------------------------------------------------------------


class TestSearchShorts:
    def test_shorts_valid_returns_200(self, client: TestClient):
        r = client.post("/search/shorts?query=receita+rapida", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["search_type"] == "shorts"
        assert body["query"] == "receita rapida"

    def test_shorts_with_max_results(self, client: TestClient):
        r = client.post(
            "/search/shorts?query=lofi&max_results=30",
            headers=HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["max_results"] == 30

    def test_shorts_missing_query_returns_422(self, client: TestClient):
        r = client.post("/search/shorts", headers=HEADERS)
        assert r.status_code == 422

    def test_shorts_max_results_out_of_range_returns_422(self, client: TestClient):
        r = client.post(
            "/search/shorts?query=test&max_results=100",
            headers=HEADERS,
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /search/related-videos
# ---------------------------------------------------------------------------


class TestSearchRelatedVideos:
    def test_related_videos_valid_returns_200(self, client: TestClient):
        r = client.post(
            "/search/related-videos?video_id=dQw4w9WgXcQ",
            headers=HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["search_type"] == "related_videos"
        assert body["video_id"] == "dQw4w9WgXcQ"

    def test_related_videos_with_max_results(self, client: TestClient):
        r = client.post(
            "/search/related-videos?video_id=dQw4w9WgXcQ&max_results=20",
            headers=HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["max_results"] == 20

    def test_related_videos_missing_param_returns_422(self, client: TestClient):
        r = client.post("/search/related-videos", headers=HEADERS)
        assert r.status_code == 422

    def test_related_videos_max_results_too_high_returns_422(self, client: TestClient):
        r = client.post(
            "/search/related-videos?video_id=dQw4w9WgXcQ&max_results=51",
            headers=HEADERS,
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /jobs  (list)
# ---------------------------------------------------------------------------


class TestListJobs:
    def test_list_jobs_returns_200(self, client: TestClient):
        r = client.get("/jobs", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "jobs" in body
        assert "total" in body
        assert isinstance(body["jobs"], list)

    def test_list_jobs_with_limit(self, client: TestClient):
        r = client.get("/jobs?limit=10", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "jobs" in body

    def test_list_jobs_limit_too_high_returns_422(self, client: TestClient):
        r = client.get("/jobs?limit=201", headers=HEADERS)
        assert r.status_code == 422

    def test_list_jobs_limit_zero_returns_422(self, client: TestClient):
        r = client.get("/jobs?limit=0", headers=HEADERS)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}
# ---------------------------------------------------------------------------


class TestGetJob:
    def test_get_job_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = _make_mock_job("ys_ok_001")
        r = client.get("/jobs/ys_ok_001", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "ys_ok_001"

    def test_get_job_not_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = None
        r = client.get("/jobs/ys_nonexistent", headers=HEADERS)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /jobs/{job_id}
# ---------------------------------------------------------------------------


class TestDeleteJob:
    def test_delete_job_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = _make_mock_job("ys_del_001")
        r = client.delete("/jobs/ys_del_001", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["job_id"] == "ys_del_001"
        assert "message" in body

    def test_delete_job_not_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = None
        r = client.delete("/jobs/ys_nonexistent", headers=HEADERS)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/download
# ---------------------------------------------------------------------------


class TestDownloadJob:
    def test_download_not_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = None
        r = client.get("/jobs/ys_xyz/download", headers=HEADERS)
        assert r.status_code == 404

    def test_download_not_ready(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = _make_mock_job(
            "ys_pending_001", status="pending", result=None,
        )
        r = client.get("/jobs/ys_pending_001/download", headers=HEADERS)
        assert r.status_code == 425

    def test_download_completed(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = _make_mock_job(
            "ys_done_001",
            status="completed",
            result={"videos": [{"id": "v1", "title": "Video 1"}]},
        )
        r = client.get("/jobs/ys_done_001/download", headers=HEADERS)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "application/json" in ct
        assert "content-disposition" in r.headers


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/wait
# ---------------------------------------------------------------------------


class TestWaitJob:
    def test_wait_not_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = None
        r = client.get("/jobs/ys_nonexistent/wait", headers=HEADERS)
        assert r.status_code == 404

    def test_wait_already_completed(
        self, client: TestClient, mock_job_store: MagicMock,
    ):
        mock_job_store.get_job.return_value = _make_mock_job("ys_done_002")
        r = client.get("/jobs/ys_done_002/wait?timeout=1", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "completed"

    def test_wait_timeout_invalid_returns_422(self, client: TestClient):
        r = client.get("/jobs/ys_any/wait?timeout=0", headers=HEADERS)
        assert r.status_code == 422

    def test_wait_timeout_too_high_returns_422(self, client: TestClient):
        r = client.get("/jobs/ys_any/wait?timeout=3601", headers=HEADERS)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /admin/stats
# ---------------------------------------------------------------------------


class TestAdminStats:
    def test_stats_returns_200(self, client: TestClient):
        r = client.get("/admin/stats", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "total_jobs" in body
        assert "by_status" in body
        assert "celery" in body

    def test_stats_celery_structure(self, client: TestClient):
        r = client.get("/admin/stats", headers=HEADERS)
        body = r.json()
        celery = body["celery"]
        assert "active_workers" in celery
        assert "active_tasks" in celery
        assert "broker" in celery
        assert "backend" in celery
        assert "queue" in celery


# ---------------------------------------------------------------------------
# GET /admin/queue
# ---------------------------------------------------------------------------


class TestAdminQueue:
    def test_queue_returns_200(self, client: TestClient):
        r = client.get("/admin/queue", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "active_workers" in body
        assert "registered_tasks" in body
        assert "active_tasks" in body
        assert "scheduled_tasks" in body
        assert "is_running" in body


# ---------------------------------------------------------------------------
# POST /admin/cleanup
# ---------------------------------------------------------------------------


class TestAdminCleanup:
    def test_basic_cleanup_returns_200(self, client: TestClient):
        r = client.post("/admin/cleanup", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "jobs_removed" in body
        assert "message" in body

    def test_deep_cleanup_returns_200(self, client: TestClient):
        r = client.post("/admin/cleanup?deep=true", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "redis_flushed" in body
        assert "message" in body

    def test_cleanup_with_celery_purge_returns_200(self, client: TestClient):
        r = client.post(
            "/admin/cleanup?deep=true&purge_celery_queue=true",
            headers=HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert "celery_queue_purged" in body


# ---------------------------------------------------------------------------
# GET /admin/metrics
# ---------------------------------------------------------------------------


class TestAdminMetrics:
    def test_metrics_returns_200(self, client: TestClient):
        r = client.get("/admin/metrics", headers=HEADERS)
        assert r.status_code == 200

    def test_metrics_content_type_plain_text(self, client: TestClient):
        r = client.get("/admin/metrics", headers=HEADERS)
        ct = r.headers.get("content-type", "")
        assert "text/plain" in ct

    def test_metrics_prometheus_format(self, client: TestClient):
        r = client.get("/admin/metrics", headers=HEADERS)
        text = r.text
        assert "youtube_search_jobs_total" in text


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestAuth:
    def test_missing_api_key_returns_401(self):
        with patch(
            "common.redis_utils.resilient_store.ResilientRedisStore._test_connection"
        ):
            app, verify_api_key = load_app("se6-youtube-search")
            from app.infrastructure.dependencies import job_store

            app.dependency_overrides.pop(verify_api_key, None)
            mock_store = MagicMock()
            job_store.set(mock_store)
            try:
                with TestClient(app, raise_server_exceptions=False) as c:
                    r = c.post("/search/videos?query=test")
                    assert r.status_code == 401
            finally:
                job_store.reset()
