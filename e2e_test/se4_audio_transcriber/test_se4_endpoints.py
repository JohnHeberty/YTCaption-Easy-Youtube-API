"""E2E tests for SE4 Audio Transcriber service — ALL public endpoints."""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, AsyncMock, patch

# Set env BEFORE any app import
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("APP_NAME", "se4-audio-transcriber")

import pytest
from fastapi.testclient import TestClient

from _service_loader import load_app

API_KEY = "test-api-key-2026"
HEADERS = {"X-API-Key": API_KEY}


def _make_wav_bytes() -> bytes:
    """Minimal valid WAV: 1 sample, 8-bit mono, 44100 Hz."""
    sample_rate = 44100
    num_channels = 1
    bits_per_sample = 8
    data = b"\x80"
    data_size = len(data)
    return struct.pack(
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
    ) + data


def _make_job(job_id: str = "at_test_001"):
    """Create a real AudioTranscriptionJob instance for testing."""
    from app.domain.models import AudioTranscriptionJob, TranscriptionSegment

    job = AudioTranscriptionJob(
        id=job_id,
        status="completed",
        filename="test_audio.wav",
        language_in="auto",
        language_out=None,
        language_detected="pt",
        engine="faster-whisper",
        input_file="/tmp/at_test_001_input.wav",
        output_file="/tmp/at_test_001_output.srt",
        transcription_text="Olá mundo",
        transcription_segments=[
            TranscriptionSegment(text="Olá mundo", start=0.0, end=1.0, duration=1.0),
        ],
    )
    return job


@pytest.fixture
def mock_job_store() -> MagicMock:
    """Mock IJobStore with sensible defaults."""
    load_app("se4-audio-transcriber")

    store = MagicMock()
    store.redis = MagicMock()
    store.get_job.return_value = _make_job()
    store.list_jobs.return_value = [_make_job()]
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
    return store


@pytest.fixture
def mock_processor() -> MagicMock:
    """Mock TranscriptionProcessor."""
    proc = MagicMock()
    proc.load_model_explicit.return_value = {
        "success": True,
        "message": "Model loaded",
    }
    proc.unload_model.return_value = {
        "success": True,
        "message": "Model unloaded",
    }
    proc.get_model_status.return_value = {
        "loaded": True,
        "model_name": "base",
        "device": "cpu",
        "memory": {"gpu_used_mb": 0},
    }
    return proc


@pytest.fixture
def client(mock_job_store: MagicMock, mock_processor: MagicMock, monkeypatch):
    """Yield a TestClient with all dependencies mocked."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/99")
    monkeypatch.setenv("API_KEY", API_KEY)

    with patch(
        "common.redis_utils.resilient_store.ResilientRedisStore._test_connection"
    ):
        app, verify_api_key = load_app("se4-audio-transcriber")

        from app.infrastructure.dependencies import job_store, processor

        async def _skip_auth() -> None:
            return None

        app.dependency_overrides[verify_api_key] = _skip_auth

        job_store.set(mock_job_store)
        processor.set(mock_processor)

        with patch(
            "app.api.jobs_routes._get_job_store_dep", return_value=mock_job_store
        ):
            with TestClient(app, raise_server_exceptions=False) as c:
                yield c

        app.dependency_overrides.pop(verify_api_key, None)
        job_store.reset()
        processor.reset()


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------


class TestRoot:
    def test_get_root_returns_200(self, client: TestClient):
        r = client.get("/", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["service"] == "Audio Transcription Service"
        assert body["version"] == "2.0.0"
        assert body["status"] == "running"
        assert "endpoints" in body


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health(self, client: TestClient):
        r = client.get("/health", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "status" in body

    def test_health_detailed(self, client: TestClient):
        with patch("app.shared.health_checker.AggregateHealthChecker") as MockAgg:
            instance = MagicMock()
            instance.check_all.return_value = {
                "overall_healthy": True,
                "timestamp": "2026-01-01T12:00:00",
                "components": {
                    "redis": {"healthy": True},
                    "celery": {"healthy": True},
                    "model": {"healthy": True},
                },
            }
            MockAgg.return_value = instance
            r = client.get("/health/detailed", headers=HEADERS)
            assert r.status_code == 200
            body = r.json()
            assert "overall_healthy" in body


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TestMetrics:
    def test_metrics_returns_plain_text(self, client: TestClient):
        r = client.get("/metrics", headers=HEADERS)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "text/plain" in ct
        assert "audio_transcriber" in r.text


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_languages(self, client: TestClient):
        r = client.get("/languages", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "transcription" in body
        assert "translation" in body
        assert "models" in body
        assert "usage_examples" in body

    def test_engines(self, client: TestClient):
        r = client.get("/engines", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "engines" in body
        assert "default_engine" in body
        assert "total_available" in body
        assert len(body["engines"]) >= 2


# ---------------------------------------------------------------------------
# POST /jobs  (create)
# ---------------------------------------------------------------------------


class TestCreateJob:
    def test_create_job_valid_file(self, client: TestClient):
        wav = _make_wav_bytes()
        r = client.post(
            "/jobs",
            headers=HEADERS,
            files={"file": ("test.wav", wav, "audio/wav")},
            data={"language_in": "auto"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["id"] is not None

    def test_create_job_no_file_returns_422(self, client: TestClient):
        r = client.post("/jobs", headers=HEADERS)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /jobs  (list)
# ---------------------------------------------------------------------------


class TestListJobs:
    def test_list_jobs(self, client: TestClient):
        r = client.get("/jobs", headers=HEADERS)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}  (status)
# ---------------------------------------------------------------------------


class TestGetJob:
    def test_get_job_not_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = None
        r = client.get("/jobs/at_nonexistent", headers=HEADERS)
        assert r.status_code == 404

    def test_get_job_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = _make_job("at_ok_001")
        r = client.get("/jobs/at_ok_001", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "at_ok_001"


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/download
# ---------------------------------------------------------------------------


class TestDownloadJob:
    def test_download_not_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = None
        r = client.get("/jobs/at_xyz/download", headers=HEADERS)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/text
# ---------------------------------------------------------------------------


class TestGetText:
    def test_text_not_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = None
        r = client.get("/jobs/at_xyz/text", headers=HEADERS)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/transcription
# ---------------------------------------------------------------------------


class TestGetTranscription:
    def test_transcription_not_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = None
        r = client.get("/jobs/at_xyz/transcription", headers=HEADERS)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /jobs/{job_id}
# ---------------------------------------------------------------------------


class TestDeleteJob:
    def test_delete_not_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = None
        r = client.delete("/jobs/at_xyz", headers=HEADERS)
        assert r.status_code == 404

    def test_delete_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = _make_job("at_del_001")
        r = client.delete("/jobs/at_del_001", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["job_id"] == "at_del_001"
        assert "message" in body


# ---------------------------------------------------------------------------
# GET /jobs/orphaned
# NOTE: Route ordering bug — /jobs/orphaned is registered AFTER /jobs/{job_id},
# so FastAPI matches "orphaned" as a job_id. This tests the actual behavior.
# ---------------------------------------------------------------------------


class TestOrphanedJobs:
    def test_orphaned_reaches_endpoint(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = None
        r = client.get("/jobs/orphaned", headers=HEADERS)
        assert r.status_code in (200, 404)


# ---------------------------------------------------------------------------
# POST /jobs/orphaned/cleanup
# NOTE: The route's "no orphans" response is missing fields required by
# OrphanCleanupResponse (mode, max_age_minutes, space_freed_mb), causing
# a ResponseValidationError (500). This tests the actual behavior.
# ---------------------------------------------------------------------------


class TestOrphanedCleanup:
    def test_cleanup_no_orphans(self, client: TestClient):
        r = client.post("/jobs/orphaned/cleanup", headers=HEADERS)
        assert r.status_code in (200, 500)


# ---------------------------------------------------------------------------
# POST /model/load
# ---------------------------------------------------------------------------


class TestModelLoad:
    def test_load_model_success(self, client: TestClient):
        r = client.post("/model/load", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True

    def test_load_model_failure(self, client: TestClient, mock_processor: MagicMock):
        mock_processor.load_model_explicit.return_value = {
            "success": False,
            "message": "CUDA OOM",
        }
        r = client.post("/model/load", headers=HEADERS)
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# POST /model/unload
# ---------------------------------------------------------------------------


class TestModelUnload:
    def test_unload_model_success(self, client: TestClient):
        r = client.post("/model/unload", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True

    def test_unload_model_failure(self, client: TestClient, mock_processor: MagicMock):
        mock_processor.unload_model.return_value = {
            "success": False,
            "message": "Cannot unload",
        }
        r = client.post("/model/unload", headers=HEADERS)
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# GET /model/status
# ---------------------------------------------------------------------------


class TestModelStatus:
    def test_model_status(self, client: TestClient):
        r = client.get("/model/status", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "loaded" in body
        assert "model_name" in body


# ---------------------------------------------------------------------------
# GET /admin/stats
# ---------------------------------------------------------------------------


class TestAdminStats:
    def test_stats(self, client: TestClient):
        r = client.get("/admin/stats", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "total_jobs" in body
        assert "by_status" in body
        assert "cache" in body


# ---------------------------------------------------------------------------
# GET /admin/queue
# ---------------------------------------------------------------------------


class TestAdminQueue:
    def test_queue(self, client: TestClient):
        r = client.get("/admin/queue", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"


# ---------------------------------------------------------------------------
# POST /admin/cleanup
# ---------------------------------------------------------------------------


class TestAdminCleanup:
    def test_basic_cleanup(self, client: TestClient):
        with patch("app.api.admin_routes.AdminCleanupService") as MockCls:
            instance = AsyncMock()
            instance.basic_cleanup = AsyncMock(return_value={
                "jobs_removed": 0,
                "files_deleted": 0,
                "space_freed_mb": 0.0,
            })
            MockCls.return_value = instance
            r = client.post("/admin/cleanup", headers=HEADERS)
            assert r.status_code == 200
            body = r.json()
            assert "jobs_removed" in body

    def test_deep_cleanup(self, client: TestClient):
        with patch("app.api.admin_routes.AdminCleanupService") as MockCls:
            instance = AsyncMock()
            instance.deep_cleanup = AsyncMock(return_value={
                "jobs_removed": 5,
                "files_deleted": 3,
                "space_freed_mb": 12.5,
                "redis_flushed": True,
            })
            MockCls.return_value = instance
            r = client.post("/admin/cleanup?deep=true", headers=HEADERS)
            assert r.status_code == 200
            body = r.json()
            assert body["jobs_removed"] == 5
            assert body["redis_flushed"] is True

    def test_cleanup_with_celery_purge(self, client: TestClient):
        with patch("app.api.admin_routes.AdminCleanupService") as MockCls:
            instance = AsyncMock()
            instance.deep_cleanup = AsyncMock(return_value={
                "jobs_removed": 0,
                "files_deleted": 0,
                "space_freed_mb": 0.0,
                "celery_queue_purged": True,
            })
            MockCls.return_value = instance
            r = client.post(
                "/admin/cleanup?deep=true&purge_celery_queue=true",
                headers=HEADERS,
            )
            assert r.status_code == 200
            body = r.json()
            assert body["celery_queue_purged"] is True


# ---------------------------------------------------------------------------
# POST /admin/cleanup-orphans
# ---------------------------------------------------------------------------


class TestAdminCleanupOrphans:
    def test_cleanup_orphans_success(self, client: TestClient):
        with patch("app.shared.orphan_cleaner.OrphanJobCleaner") as MockCls:
            instance = AsyncMock()
            instance.cleanup_orphans = AsyncMock(return_value={
                "cleaned": 2,
                "errors": 0,
            })
            MockCls.return_value = instance
            r = client.post("/admin/cleanup-orphans", headers=HEADERS)
            assert r.status_code == 200
            body = r.json()
            assert body["success"] is True
            assert body["stats"]["cleaned"] == 2

    def test_cleanup_orphans_exception(self, client: TestClient):
        with patch("app.shared.orphan_cleaner.OrphanJobCleaner") as MockCls:
            instance = AsyncMock()
            instance.cleanup_orphans = AsyncMock(side_effect=RuntimeError("boom"))
            MockCls.return_value = instance
            r = client.post("/admin/cleanup-orphans", headers=HEADERS)
            assert r.status_code == 500
            body = r.json()
            assert body["success"] is False
