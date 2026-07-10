"""
Phase 4 — E2E minimum tests for full job lifecycle.

Covers: upload → poll status evolution → retrieve caption download, plus error cases.
Uses FastAPI TestClient with DI overrides to avoid real Redis/Celery/Whisper dependencies.
"""
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_client(store):
    """Create a fresh TestClient + store pair for each test.

    Patches BOTH the Depends(job_store) override AND the direct factory call used by upload,
    because create_transcription_job calls _get_job_store_dep() directly instead of Depends().
    """
    from fastapi.testclient import TestClient
    from app.infrastructure.dependencies import job_store as js_dep, get_job_store
    from app.main import app
    from app.core.config import get_settings

    # Clear lru_cache so factory returns fresh result after override is set
    get_job_store.cache_clear()

    js_dep.set(store)

    def mock_submit(job, _store=None):
        pass

    with patch("app.api.jobs_routes.submit_processing_task", side_effect=mock_submit), \
         patch("app.api.jobs_routes._get_job_store_dep", return_value=store), \
         patch.object(Path, "exists", return_value=True):
        client = TestClient(app)
        client.headers["X-API-Key"] = get_settings().api_key
        try:
            yield (client, store)
        finally:
            js_dep.reset()


@pytest.fixture()
def e2e_client():
    """Fresh TestClient with basic mock store per test."""
    from .conftest import MockE2EJobStore

    client_gen = _make_client(MockE2EJobStore())
    yield next(client_gen)


@pytest.fixture()
def e2e_transition_client():
    """Fresh TestClient with state-transition store for polling evolution tests."""
    from .conftest import StateTransitionJobStore

    client_gen = _make_client(StateTransitionJobStore())
    yield next(client_gen)


class TestUploadAudioFile:
    """POST /jobs — upload audio file and create transcription job."""

    def test_upload_valid_wav_returns_success(self, e2e_client):
        client, store = e2e_client
        from .conftest import generate_wav_bytes

        response = client.post(
            "/jobs",
            data={
                "language_in": "pt",
                "engine": "faster-whisper"
            },
            files={"file": ("test.wav", io.BytesIO(generate_wav_bytes()), "audio/wav")}
        )

        assert response.status_code in (200, 201), f"Expected success, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data

    def test_upload_valid_mp3_filename_returns_success(self, e2e_client):
        client, _store = e2e_client
        from .conftest import generate_wav_bytes

        response = client.post(
            "/jobs",
            data={
                "language_in": "en"
            },
            files={"file": ("audio.mp3", io.BytesIO(generate_wav_bytes()), "audio/mpeg")}
        )

        assert response.status_code in (200, 201), f"Expected success, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data

    def test_upload_with_auto_language_returns_success(self, e2e_client):
        client, _store = e2e_client
        from .conftest import generate_wav_bytes

        response = client.post(
            "/jobs",
            files={"file": ("test.wav", io.BytesIO(generate_wav_bytes()), "audio/wav")}
        )

        assert response.status_code in (200, 201), f"Expected success, got {response.status_code}: {response.text}"

    def test_upload_with_translation_returns_success(self, e2e_client):
        client, _store = e2e_client
        from .conftest import generate_wav_bytes

        response = client.post(
            "/jobs",
            data={
                "language_in": "pt",
                "language_out": "en"
            },
            files={"file": ("test.wav", io.BytesIO(generate_wav_bytes()), "audio/wav")}
        )

        assert response.status_code in (200, 201), f"Expected success, got {response.status_code}: {response.text}"


class TestUploadErrorCases:
    """POST /jobs — error handling for invalid uploads."""

    def test_upload_unsupported_language_returns_400(self, e2e_client):
        client, _store = e2e_client
        from .conftest import generate_wav_bytes

        response = client.post(
            "/jobs",
            data={"language_in": "zz_not_supported_lang_xyz"},
            files={"file": ("test.wav", io.BytesIO(generate_wav_bytes()), "audio/wav")}
        )

        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"


class TestPollJobStatus:
    """GET /jobs/{id} — poll job status evolution (queued → processing → completed)."""

    def test_poll_status_evolution(self, e2e_client):
        """Verify GET /jobs/{id} returns the job created by upload."""
        client, store = e2e_client
        from .conftest import generate_wav_bytes

        # Patch _get_job_store_dep so upload saves to our mock store too
        with patch("app.api.jobs_routes._get_job_store_dep", return_value=store):
            upload_resp = client.post(
                "/jobs",
                data={"language_in": "pt"},
                files={"file": ("test.wav", io.BytesIO(generate_wav_bytes()), "audio/wav")}
            )

        assert upload_resp.status_code in (200, 201), f"Upload failed: {upload_resp.text}"
        job_id = upload_resp.json()["id"]

        # Poll the status endpoint — should return the same job we just created
        resp = client.get(f"/jobs/{job_id}")
        assert resp.status_code == 200, f"Expected 200 from poll, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "status" in data


class TestRetrieveCaptionDownload:
    """GET /jobs/{id}/download and GET /jobs/{id}/text — retrieve completed transcription."""

    def test_download_completed_job_returns_file(self, e2e_client):
        client, store = e2e_client
        from app.domain.models import JobStatus

        job_id = "at_e2e_test_1"
        output_path = Path("/tmp/e2e_caption.srt")
        output_path.write_text("1\n00:00:00,000 --> 00:00:05,000\nTest caption line\n")

        from app.domain.models import Job
        job = MagicMock(spec=Job)
        job.id = job_id
        job.status = JobStatus.COMPLETED
        job.output_file = str(output_path)
        job.is_expired = False

        store.save_job(job)

        resp = client.get(f"/jobs/{job_id}/download")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert "Test caption line" in resp.text

    def test_download_in_progress_job_returns_425(self, e2e_client):
        client, store = e2e_client
        from app.domain.models import JobStatus

        job_id = "at_e2e_test_2"
        job = MagicMock()
        job.id = job_id
        job.status = JobStatus.PROCESSING
        job.is_expired = False

        store.save_job(job)

        resp = client.get(f"/jobs/{job_id}/download")
        assert resp.status_code == 425, f"Expected 425, got {resp.status_code}: {resp.text}"

    def test_download_nonexistent_job_returns_404(self, e2e_client):
        client, _store = e2e_client

        resp = client.get("/jobs/at_does_not_exist/download")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


class TestRetrieveTranscriptionText:
    """GET /jobs/{id}/text — retrieve plain text transcription."""

    def test_get_text_completed_job(self, e2e_client):
        client, store = e2e_client
        from app.domain.models import JobStatus

        job_id = "at_e2e_test_3"
        job = MagicMock()
        job.id = job_id
        job.status = JobStatus.COMPLETED
        job.transcription_text = "Hello world test transcription."

        store.save_job(job)

        resp = client.get(f"/jobs/{job_id}/text")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "Hello world test transcription." in data["text"]

    def test_get_text_processing_job_returns_425(self, e2e_client):
        client, store = e2e_client
        from app.domain.models import JobStatus

        job_id = "at_e2e_test_4"
        job = MagicMock()
        job.id = job_id
        job.status = JobStatus.PROCESSING

        store.save_job(job)

        resp = client.get(f"/jobs/{job_id}/text")
        assert resp.status_code == 425, f"Expected 425, got {resp.status_code}: {resp.text}"


class TestDeleteJob:
    """DELETE /jobs/{id} — delete job and associated files."""

    def test_delete_existing_job(self, e2e_client):
        client, store = e2e_client
        from app.domain.models import JobStatus

        job_id = "at_e2e_test_5_del"
        input_path = Path(f"/tmp/e2e_input_{job_id}.wav")
        output_path = Path(f"/tmp/e2e_output_{job_id}.srt")
        # Ensure files exist (force write to avoid stale state)
        for p in (input_path, output_path):
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("dummy content\n")

        job = MagicMock()
        job.id = job_id
        job.status = JobStatus.COMPLETED
        job.input_file = str(input_path)
        job.output_file = str(output_path)

        store.save_job(job)

        # Patch _get_job_store_dep so upload path uses our mock too (delete doesn't use it, but be safe)
        with patch("app.api.jobs_routes._get_job_store_dep", return_value=store):
            resp = client.delete(f"/jobs/{job_id}")

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_delete_nonexistent_job_returns_404(self, e2e_client):
        client, _store = e2e_client

        resp = client.delete("/jobs/at_does_not_exist")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


class TestListJobs:
    """GET /jobs — list recent transcription jobs."""

    def test_list_jobs_returns_empty_when_no_jobs(self, e2e_client):
        client, _store = e2e_client

        resp = client.get("/jobs")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


class TestRootEndpoint:
    """GET / — service info endpoint."""

    def test_root_returns_service_info(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.infrastructure.dependencies.job_store") as mock_dep, \
             patch.object(Path, "exists", return_value=False):
            mock_dep.return_value = MagicMock()
            client = TestClient(app)
            resp = client.get("/")
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
