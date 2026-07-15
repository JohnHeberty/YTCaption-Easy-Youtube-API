"""E2E tests for SE3 Audio Normalization service — ALL public endpoints."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, AsyncMock, patch

os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("APP_NAME", "se3-audio-normalization")
os.environ.setdefault("LOG_LEVEL", "DEBUG")

import pytest
from fastapi.testclient import TestClient

from _service_loader import load_app

API_KEY = "test-api-key-2026"
HEADERS = {"X-API-Key": API_KEY}


def _make_wav_bytes() -> bytes:
    """Minimal valid WAV: 1 sample, 8-bit mono, 44100 Hz."""
    import struct

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


def _make_mock_job(job_id: str = "an_test_001") -> Any:
    """Create a real AudioNormJob that passes Pydantic response validation."""
    from app.core.models import AudioNormJob
    from common.job_utils.models import JobStatus

    job = AudioNormJob(
        id=job_id,
        status=JobStatus.COMPLETED,
        filename="test_audio.wav",
        input_file=f"/tmp/{job_id}_input.wav",
        output_file=f"/tmp/{job_id}_output.webm",
        file_size_input=1024,
        file_size_output=2048,
        remove_noise=True,
        convert_to_mono=True,
        apply_highpass_filter=False,
        set_sample_rate_16k=True,
        isolate_vocals=False,
    )
    job.mark_as_completed(message="done")
    return job


@pytest.fixture
def mock_job_store() -> MagicMock:
    """Mock AudioNormJobStore with sensible defaults."""
    store = MagicMock()
    store.redis = MagicMock()
    store.redis.ping.return_value = True
    store.get_job.return_value = None
    store.list_jobs.return_value = []
    store.delete_job.return_value = True
    store.save_job.side_effect = lambda job: job
    store.update_job.side_effect = lambda job: job
    store.get_stats.return_value = {
        "total_jobs": 0,
        "by_status": {},
    }
    store.get_queue_info = AsyncMock(return_value={"processing": [], "completed": []})
    store.cleanup_expired.return_value = 0
    store.cleanup_all.return_value = 0
    store.start_cleanup_task = AsyncMock()
    store.stop_cleanup_task = AsyncMock()
    return store


@pytest.fixture
def mock_audio_processor() -> MagicMock:
    """Mock AudioProcessor."""
    proc = MagicMock()
    proc.process_audio_job = AsyncMock(return_value={"success": True})
    return proc


@pytest.fixture
def client(mock_job_store: MagicMock, mock_audio_processor: MagicMock, tmp_path: Path):
    """Yield a TestClient with all dependencies mocked."""
    with patch(
        "common.redis_utils.resilient_store.ResilientRedisStore._test_connection"
    ):
        app, verify_api_key = load_app("se3-audio-normalization")
        from app.infrastructure.dependencies import job_store, audio_processor

        async def _skip_auth() -> None:
            return None

        app.dependency_overrides[verify_api_key] = _skip_auth
        job_store.set(mock_job_store)
        audio_processor.set(mock_audio_processor)

        with (
            patch("app.main.get_upload_dir", return_value=tmp_path),
            patch(
                "app.services.job_service.JobSubmissionService.submit_with_fallback",
                new_callable=AsyncMock,
            ),
            patch(
                "common.health_utils.ServiceHealthChecker.check_ffmpeg"
            ) as mock_ffmpeg,
        ):
            from common.health_utils import CheckResult

            mock_ffmpeg.return_value = CheckResult(
                name="ffmpeg", status="ok", detail="ffmpeg version 6.0"
            )

            with TestClient(app, raise_server_exceptions=False) as c:
                yield c

        app.dependency_overrides.pop(verify_api_key, None)
        job_store.reset()
        audio_processor.reset()


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------


class TestRoot:
    def test_get_root_returns_200(self, client: TestClient):
        r = client.get("/", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["service"] == "Audio Normalization Service"
        assert body["version"] == "2.0.0"
        assert body["status"] == "running"
        assert "endpoints" in body
        assert "health" in body["endpoints"]
        assert "jobs" in body["endpoints"]
        assert "admin" in body["endpoints"]

    def test_root_without_auth_header(self, client: TestClient):
        r = client.get("/")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_200(self, client: TestClient):
        r = client.get("/health", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"
        assert body["service"] == "audio-normalization"
        assert body["version"] == "2.0.0"
        assert "timestamp" in body
        assert "checks" in body
        assert "redis" in body["checks"]
        assert body["checks"]["redis"]["status"] == "ok"
        assert "disk" in body["checks"]
        assert body["checks"]["disk"]["status"] in ("ok", "warning")
        assert "ffmpeg" in body["checks"]
        assert body["checks"]["ffmpeg"]["status"] == "ok"

    def test_health_without_auth(self, client: TestClient):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_unhealthy_when_redis_down(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.redis.ping.return_value = False
        r = client.get("/health", headers=HEADERS)
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "unhealthy"
        assert body["checks"]["redis"]["status"] == "error"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TestMetrics:
    def test_metrics_returns_plain_text(self, client: TestClient):
        r = client.get("/metrics", headers=HEADERS)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "text/plain" in ct
        assert "audio_normalization_jobs_total" in r.text
        assert "audio_normalization_jobs_store_total" in r.text

    def test_metrics_without_auth(self, client: TestClient):
        r = client.get("/metrics")
        assert r.status_code == 200

    def test_metrics_with_jobs(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_stats.return_value = {
            "total_jobs": 5,
            "by_status": {"completed": 3, "failed": 2},
        }
        r = client.get("/metrics", headers=HEADERS)
        assert r.status_code == 200
        assert 'audio_normalization_jobs_total{status="completed"} 3' in r.text
        assert 'audio_normalization_jobs_total{status="failed"} 2' in r.text
        assert "audio_normalization_jobs_store_total 5" in r.text


# ---------------------------------------------------------------------------
# POST /jobs (create)
# ---------------------------------------------------------------------------


class TestCreateJob:
    def test_create_job_valid_file(self, client: TestClient):
        wav = _make_wav_bytes()
        r = client.post(
            "/jobs",
            headers=HEADERS,
            files={"file": ("test.wav", wav, "audio/wav")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["id"] is not None
        assert body["id"].startswith("an_")
        assert body["filename"] == "test.wav"
        assert body["status"] in ("queued", "processing", "completed")

    def test_create_job_no_file_returns_422(self, client: TestClient):
        r = client.post("/jobs", headers=HEADERS)
        assert r.status_code == 422

    def test_create_job_empty_file_returns_400(self, client: TestClient):
        r = client.post(
            "/jobs",
            headers=HEADERS,
            files={"file": ("empty.wav", b"", "audio/wav")},
        )
        assert r.status_code == 400

    def test_create_job_with_all_params(self, client: TestClient):
        wav = _make_wav_bytes()
        r = client.post(
            "/jobs",
            headers=HEADERS,
            files={"file": ("test.wav", wav, "audio/wav")},
            data={
                "remove_noise": "true",
                "convert_to_mono": "true",
                "apply_highpass_filter": "true",
                "set_sample_rate_16k": "true",
                "isolate_vocals": "true",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["remove_noise"] is True
        assert body["convert_to_mono"] is True
        assert body["apply_highpass_filter"] is True
        assert body["set_sample_rate_16k"] is True
        assert body["isolate_vocals"] is True

    def test_create_job_with_false_params(self, client: TestClient):
        wav = _make_wav_bytes()
        r = client.post(
            "/jobs",
            headers=HEADERS,
            files={"file": ("test.wav", wav, "audio/wav")},
            data={
                "remove_noise": "false",
                "convert_to_mono": "false",
                "apply_highpass_filter": "false",
                "set_sample_rate_16k": "false",
                "isolate_vocals": "false",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["remove_noise"] is False
        assert body["convert_to_mono"] is False

    def test_create_job_invalid_boolean_returns_400(self, client: TestClient):
        wav = _make_wav_bytes()
        r = client.post(
            "/jobs",
            headers=HEADERS,
            files={"file": ("test.wav", wav, "audio/wav")},
            data={"remove_noise": "invalid_value"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /jobs (list)
# ---------------------------------------------------------------------------


class TestListJobs:
    def test_list_jobs_empty(self, client: TestClient):
        r = client.get("/jobs", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        assert len(body) == 0

    def test_list_jobs_with_results(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.list_jobs.return_value = [
            _make_mock_job("an_list_001"),
            _make_mock_job("an_list_002"),
        ]
        r = client.get("/jobs", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 2
        assert body[0]["id"] == "an_list_001"
        assert body[1]["id"] == "an_list_002"

    def test_list_jobs_with_limit(self, client: TestClient):
        r = client.get("/jobs?limit=5", headers=HEADERS)
        assert r.status_code == 200

    def test_list_jobs_limit_too_low(self, client: TestClient):
        r = client.get("/jobs?limit=0", headers=HEADERS)
        assert r.status_code == 422

    def test_list_jobs_limit_too_high(self, client: TestClient):
        r = client.get("/jobs?limit=300", headers=HEADERS)
        assert r.status_code == 422

    def test_list_jobs_without_auth(self, client: TestClient):
        r = client.get("/jobs")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /jobs/{job_id} (status)
# ---------------------------------------------------------------------------


class TestGetJob:
    def test_get_job_not_found(self, client: TestClient):
        r = client.get("/jobs/an_nonexistent", headers=HEADERS)
        assert r.status_code in (404, 500)

    def test_get_job_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = _make_mock_job("an_ok_001")
        r = client.get("/jobs/an_ok_001", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "an_ok_001"
        assert body["status"] == "completed"
        assert body["filename"] == "test_audio.wav"

    def test_get_job_invalid_id_format(self, client: TestClient):
        r = client.get("/jobs/invalid id with spaces", headers=HEADERS)
        assert r.status_code == 400

    def test_get_job_special_chars(self, client: TestClient):
        r = client.get("/jobs/an@#$%", headers=HEADERS)
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/download
# ---------------------------------------------------------------------------


class TestDownloadJob:
    def test_download_not_found(self, client: TestClient):
        r = client.get("/jobs/an_xyz/download", headers=HEADERS)
        assert r.status_code in (404, 500)

    def test_download_invalid_id(self, client: TestClient):
        r = client.get("/jobs/invalid id/download", headers=HEADERS)
        assert r.status_code == 400

    def test_download_job_not_completed(self, client: TestClient, mock_job_store: MagicMock, tmp_path: Path):
        from app.core.models import AudioNormJob
        from common.job_utils.models import JobStatus

        job = AudioNormJob(
            id="an_pending_001",
            status=JobStatus.QUEUED,
            filename="test.wav",
        )
        mock_job_store.get_job.return_value = job
        r = client.get("/jobs/an_pending_001/download", headers=HEADERS)
        assert r.status_code in (425, 404, 500)

    def test_download_job_completed_with_output(self, client: TestClient, mock_job_store: MagicMock, tmp_path: Path):
        from app.core.models import AudioNormJob
        from common.job_utils.models import JobStatus

        output_file = tmp_path / "output.webm"
        output_file.write_bytes(b"fake-audio-data")
        job = AudioNormJob(
            id="an_done_001",
            status=JobStatus.COMPLETED,
            filename="test.wav",
            output_file=str(output_file),
        )
        mock_job_store.get_job.return_value = job
        r = client.get("/jobs/an_done_001/download", headers=HEADERS)
        assert r.status_code == 200
        assert len(r.content) > 0


# ---------------------------------------------------------------------------
# DELETE /jobs/{job_id}
# ---------------------------------------------------------------------------


class TestDeleteJob:
    def test_delete_not_found(self, client: TestClient):
        r = client.delete("/jobs/an_xyz", headers=HEADERS)
        assert r.status_code in (404, 500)

    def test_delete_invalid_id(self, client: TestClient):
        r = client.delete("/jobs/invalid id!", headers=HEADERS)
        assert r.status_code == 400

    def test_delete_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = _make_mock_job("an_del_001")
        r = client.delete("/jobs/an_del_001", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["job_id"] == "an_del_001"
        assert body["message"] == "Job removido com sucesso"
        assert isinstance(body["files_deleted"], int)

    def test_delete_cleans_files(self, client: TestClient, mock_job_store: MagicMock, tmp_path: Path):
        from app.core.models import AudioNormJob
        from common.job_utils.models import JobStatus

        input_file = tmp_path / "an_file_input.wav"
        input_file.write_bytes(b"input")
        output_file = tmp_path / "an_file_output.webm"
        output_file.write_bytes(b"output")
        job = AudioNormJob(
            id="an_file_001",
            status=JobStatus.COMPLETED,
            filename="test.wav",
            input_file=str(input_file),
            output_file=str(output_file),
        )
        mock_job_store.get_job.return_value = job
        r = client.delete("/jobs/an_file_001", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["files_deleted"] == 2
        assert not input_file.exists()
        assert not output_file.exists()


# ---------------------------------------------------------------------------
# POST /jobs/{job_id}/heartbeat
# ---------------------------------------------------------------------------


class TestHeartbeat:
    def test_heartbeat_not_found(self, client: TestClient):
        r = client.post("/jobs/an_xyz/heartbeat", headers=HEADERS)
        assert r.status_code in (404, 500)

    def test_heartbeat_invalid_id(self, client: TestClient):
        r = client.post("/jobs/invalid id/heartbeat", headers=HEADERS)
        assert r.status_code == 400

    def test_heartbeat_found(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_job.return_value = _make_mock_job("an_hb_001")
        r = client.post("/jobs/an_hb_001/heartbeat", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "an_hb_001"
        assert body["status"] == "ok"
        assert body["last_heartbeat"] is not None

    def test_heartbeat_updates_timestamp(self, client: TestClient, mock_job_store: MagicMock):
        job = _make_mock_job("an_hb_ts")
        job.last_heartbeat = None
        mock_job_store.get_job.return_value = job
        r = client.post("/jobs/an_hb_ts/heartbeat", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["last_heartbeat"] is not None


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
        assert "cache" in body
        assert isinstance(body["total_jobs"], int)
        assert isinstance(body["by_status"], dict)
        assert isinstance(body["cache"], dict)

    def test_stats_without_auth(self, client: TestClient):
        r = client.get("/admin/stats")
        assert r.status_code == 200

    def test_stats_with_jobs(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_stats.return_value = {
            "total_jobs": 10,
            "by_status": {"completed": 7, "failed": 3},
        }
        r = client.get("/admin/stats", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["total_jobs"] == 10
        assert body["by_status"]["completed"] == 7
        assert body["by_status"]["failed"] == 3

    def test_stats_cache_info(self, client: TestClient):
        r = client.get("/admin/stats", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "files_count" in body["cache"]
        assert "total_size_mb" in body["cache"]


# ---------------------------------------------------------------------------
# GET /admin/queue
# ---------------------------------------------------------------------------


class TestAdminQueue:
    def test_queue_returns_200(self, client: TestClient):
        r = client.get("/admin/queue", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        assert "queue" in body

    def test_queue_without_auth(self, client: TestClient):
        r = client.get("/admin/queue")
        assert r.status_code == 200

    def test_queue_contains_data(self, client: TestClient, mock_job_store: MagicMock):
        mock_job_store.get_queue_info = AsyncMock(
            return_value={"processing": ["an_001"], "completed": ["an_002"]}
        )
        r = client.get("/admin/queue", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert "processing" in body["queue"]
        assert "completed" in body["queue"]


# ---------------------------------------------------------------------------
# POST /admin/cleanup
# ---------------------------------------------------------------------------


class TestAdminCleanup:
    def test_basic_cleanup(self, client: TestClient):
        with patch(
            "app.services.cleanup_service.CleanupService.perform_basic_cleanup",
            new_callable=AsyncMock,
        ) as mock_cleanup:
            mock_cleanup.return_value = {
                "jobs_removed": 0,
                "files_deleted": 0,
                "space_freed_mb": 0.0,
                "errors": [],
            }
            r = client.post("/admin/cleanup", headers=HEADERS)
            assert r.status_code == 200
            body = r.json()
            assert "jobs_removed" in body
            assert "files_deleted" in body
            assert "space_freed_mb" in body
            assert isinstance(body["errors"], list)

    def test_deep_cleanup(self, client: TestClient):
        with patch(
            "app.services.cleanup_service.CleanupService.perform_deep_cleanup",
            new_callable=AsyncMock,
        ) as mock_cleanup:
            mock_cleanup.return_value = {
                "jobs_removed": 5,
                "files_deleted": 3,
                "space_freed_mb": 12.5,
                "errors": [],
                "redis_flushed": True,
                "message": "Deep cleanup completed",
            }
            r = client.post("/admin/cleanup?deep=true", headers=HEADERS)
            assert r.status_code == 200
            body = r.json()
            assert body["jobs_removed"] == 5
            assert body["files_deleted"] == 3
            assert body["space_freed_mb"] == 12.5
            assert body["redis_flushed"] is True

    def test_cleanup_without_auth(self, client: TestClient):
        with patch(
            "app.services.cleanup_service.CleanupService.perform_basic_cleanup",
            new_callable=AsyncMock,
        ) as mock_cleanup:
            mock_cleanup.return_value = {
                "jobs_removed": 0,
                "files_deleted": 0,
                "space_freed_mb": 0.0,
                "errors": [],
            }
            r = client.post("/admin/cleanup")
            assert r.status_code == 200

    def test_cleanup_with_errors(self, client: TestClient):
        with patch(
            "app.services.cleanup_service.CleanupService.perform_basic_cleanup",
            new_callable=AsyncMock,
        ) as mock_cleanup:
            mock_cleanup.return_value = {
                "jobs_removed": 2,
                "files_deleted": 1,
                "space_freed_mb": 0.5,
                "errors": ["Permission denied for /tmp/stuck_file"],
            }
            r = client.post("/admin/cleanup", headers=HEADERS)
            assert r.status_code == 200
            body = r.json()
            assert len(body["errors"]) == 1
            assert "Permission denied" in body["errors"][0]
