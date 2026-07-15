from __future__ import annotations

import io
import struct
import zlib
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from _service_loader import load_app


API_KEY = "test-api-key-2026"
HEADERS = {"X-API-Key": API_KEY}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav_bytes(
    sample_rate: int = 24000,
    num_channels: int = 1,
    bits_per_sample: int = 16,
    num_samples: int = 100,
) -> bytes:
    """Create a minimal valid WAV file in memory."""
    data_size = num_samples * num_channels * (bits_per_sample // 8)
    data = b"\x00" * data_size
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
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
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + data


def _json_response(resp, expected_status: int = 200) -> dict:
    """Assert status and return parsed JSON."""
    assert resp.status_code == expected_status, (
        f"Expected {expected_status}, got {resp.status_code}: {resp.text}"
    )
    if resp.status_code == 204:
        return {}
    return resp.json()


# ---------------------------------------------------------------------------
# Fake implementations for dependency overrides
# ---------------------------------------------------------------------------

class FakeJobStore:
    """In-memory IJobStore backed by a plain dict."""

    def __init__(self) -> None:
        self._jobs: dict[str, Any] = {}

    def save_job(self, job: Any) -> None:
        self._jobs[job.id] = job

    def get_job(self, job_id: str) -> Any | None:
        return self._jobs.get(job_id)

    def update_job(self, job: Any) -> None:
        self._jobs[job.id] = job

    def list_jobs(self, limit: int = 20) -> list[Any]:
        return list(self._jobs.values())[:limit]

    def delete_job(self, job_id: str) -> bool:
        return self._jobs.pop(job_id, None) is not None


class FakeVoiceStore:
    """In-memory IVoiceStore backed by a plain dict."""

    def __init__(self) -> None:
        self._profiles: dict[str, Any] = {}

    def save_profile(self, profile: Any) -> None:
        self._profiles[profile.id] = profile

    def get_profile(self, voice_id: str) -> Any | None:
        return self._profiles.get(voice_id)

    def list_profiles(self) -> list[Any]:
        return list(self._profiles.values())

    def delete_profile(self, voice_id: str) -> bool:
        return self._profiles.pop(voice_id, None) is not None

    def profile_exists(self, voice_id: str) -> bool:
        return voice_id in self._profiles


class FakeModelManager:
    """Stub IModelManager that always reports 'loaded'."""

    def __init__(self) -> None:
        self._loaded = True

    def load_model(self) -> None:
        self._loaded = True

    def unload_model(self) -> None:
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def device(self) -> str:
        return "cpu"

    @property
    def sample_rate(self) -> int:
        return 24000

    def get_status(self) -> dict[str, Any]:
        return {"loaded": self._loaded, "device": "cpu", "sample_rate": 24000}

    def generate(self, text: str, audio_prompt_path: str | None = None,
                 exaggeration: float = 0.5, temperature: float = 0.8,
                 cfg_weight: float = 0.5) -> Any:
        return "fake_wav_tensor"


class FakeVoiceManager:
    """Stub VoiceProfileManager wrapping a FakeVoiceStore."""

    def __init__(self, store: FakeVoiceStore) -> None:
        self._store = store

    def get_profile(self, voice_id: str) -> Any:
        from app.domain.exceptions import VoiceProfileNotFound
        p = self._store.get_profile(voice_id)
        if not p:
            raise VoiceProfileNotFound(voice_id)
        return p

    def list_profiles(self) -> list[Any]:
        return self._store.list_profiles()

    def create_profile(self, name: str, file_content: bytes, description: str = "") -> Any:
        from app.domain.models import VoiceProfile
        import uuid
        from app.core.constants import VOICE_ID_PREFIX
        vid = f"{VOICE_ID_PREFIX}{uuid.uuid4().hex[:16]}"
        profile = VoiceProfile(
            id=vid,
            name=name,
            description=description,
            audio_path=f"/tmp/{vid}.wav",
            duration_seconds=10.0,
            sample_rate=24000,
            status="active",
        )
        self._store.save_profile(profile)
        return profile

    def delete_profile(self, voice_id: str) -> None:
        from app.domain.exceptions import VoiceProfileNotFound
        if not self._store.delete_profile(voice_id):
            raise VoiceProfileNotFound(voice_id)


# ---------------------------------------------------------------------------
# Fixture: TestClient with all dependencies overridden
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_job_store() -> FakeJobStore:
    return FakeJobStore()


@pytest.fixture()
def fake_voice_store() -> FakeVoiceStore:
    return FakeVoiceStore()


@pytest.fixture()
def client(fake_job_store: FakeJobStore, fake_voice_store: FakeVoiceStore) -> TestClient:
    """Yield a fully mocked TestClient for SE7."""
    app, verify_api_key = load_app("se7-audio-generation")

    fake_model = FakeModelManager()
    fake_gen = MagicMock()
    fake_vm = FakeVoiceManager(fake_voice_store)

    from app.infrastructure import dependencies as deps

    deps.job_store.set(fake_job_store)
    deps.voice_store.set(fake_voice_store)
    deps.model_manager.set(fake_model)
    deps.generator.set(fake_gen)
    deps.voice_manager.set(fake_vm)

    # Patch lifespan so it does not attempt Redis connection or voice seeding
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    from app import main as _main
    _original_lifespan = _main.lifespan
    _main.lifespan = _noop_lifespan

    # Patch Celery task dispatch to avoid broker connection
    _celery_task_patcher = patch(
        "app.infrastructure.celery_tasks.generate_audio_task.apply_async",
        return_value=None,
    )
    _celery_task_patcher.start()

    async def _skip_auth() -> None:
        return None

    app.dependency_overrides[verify_api_key] = _skip_auth

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.pop(verify_api_key, None)
    _celery_task_patcher.stop()
    _main.lifespan = _original_lifespan
    deps.job_store.reset()
    deps.voice_store.reset()
    deps.model_manager.reset()
    deps.generator.reset()
    deps.voice_manager.reset()


# ===================================================================
# 1. Root endpoint
# ===================================================================

class TestRootEndpoint:
    @pytest.mark.e2e
    def test_get_root_returns_200(self, client: TestClient) -> None:
        resp = client.get("/", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["status"] == "running"

    @pytest.mark.e2e
    def test_root_exempt_from_auth(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200


# ===================================================================
# 2. Health endpoint
# ===================================================================

class TestHealthEndpoint:
    @pytest.mark.e2e
    @pytest.mark.health
    def test_get_health_returns_200(self, client: TestClient) -> None:
        resp = client.get("/health", headers=HEADERS)
        data = _json_response(resp, 200)
        assert "status" in data
        assert "checks" in data

    @pytest.mark.e2e
    @pytest.mark.health
    def test_health_exempt_from_auth(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.e2e
    @pytest.mark.health
    def test_health_contains_service_name(self, client: TestClient) -> None:
        resp = client.get("/health", headers=HEADERS)
        data = resp.json()
        assert data.get("service") == "audio-generation"


# ===================================================================
# 3. Jobs — POST /jobs
# ===================================================================

class TestCreateJob:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_create_job_valid_text(self, client: TestClient) -> None:
        resp = client.post(
            "/jobs",
            data={"text": "Olá, este é um teste de geração de áudio."},
            headers=HEADERS,
        )
        data = _json_response(resp, 201)
        assert data["success"] is True
        assert data["job_id"].startswith("ag_")
        assert data["status"] == "queued"

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_create_job_with_voice_id(self, client: TestClient, fake_voice_store: FakeVoiceStore) -> None:
        from app.domain.models import VoiceProfile
        from datetime import datetime
        from common.datetime_utils import now_brazil
        vid = "vc_testvoice123"
        profile = VoiceProfile(
            id=vid, name="Test Voice", description="",
            created_at=now_brazil(), audio_path="/tmp/test.wav",
            duration_seconds=10.0, sample_rate=24000, status="active",
        )
        fake_voice_store.save_profile(profile)

        resp = client.post(
            "/jobs",
            data={"text": "Texto com voz customizada.", "voice_id": vid},
            headers=HEADERS,
        )
        data = _json_response(resp, 201)
        assert data["success"] is True

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_create_job_with_custom_params(self, client: TestClient) -> None:
        resp = client.post(
            "/jobs",
            data={
                "text": "Parâmetros customizados para o áudio.",
                "exaggeration": "0.8",
                "cfg_weight": "0.3",
                "temperature": "0.9",
            },
            headers=HEADERS,
        )
        data = _json_response(resp, 201)
        assert data["success"] is True

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_create_job_missing_text_returns_422(self, client: TestClient) -> None:
        resp = client.post("/jobs", data={}, headers=HEADERS)
        assert resp.status_code == 422

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_create_job_nonexistent_voice_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/jobs",
            data={"text": "Voz inexistente.", "voice_id": "vc_nonexistent"},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_create_job_empty_text_accepted(self, client: TestClient) -> None:
        resp = client.post("/jobs", data={"text": ""}, headers=HEADERS)
        assert resp.status_code == 201


# ===================================================================
# 4. Jobs — GET /jobs
# ===================================================================

class TestListJobs:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_list_jobs_empty(self, client: TestClient) -> None:
        resp = client.get("/jobs", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["jobs"] == []
        assert data["total"] == 0

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_list_jobs_after_creation(self, client: TestClient) -> None:
        client.post(
            "/jobs",
            data={"text": "Primeiro job."},
            headers=HEADERS,
        )
        client.post(
            "/jobs",
            data={"text": "Segundo job."},
            headers=HEADERS,
        )
        resp = client.get("/jobs", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["total"] == 2
        assert len(data["jobs"]) == 2

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_list_jobs_limit(self, client: TestClient, fake_job_store: FakeJobStore) -> None:
        from app.domain.models import AudioGenerationJob
        for i in range(5):
            job = AudioGenerationJob.create_new(text=f"job-{i}")
            fake_job_store.save_job(job)
        resp = client.get("/jobs?limit=2", headers=HEADERS)
        data = _json_response(resp, 200)
        assert len(data["jobs"]) == 2


# ===================================================================
# 5. Jobs — GET /jobs/{job_id}
# ===================================================================

class TestGetJobStatus:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_get_job_not_found(self, client: TestClient) -> None:
        resp = client.get("/jobs/nonexistent_job_id", headers=HEADERS)
        assert resp.status_code == 404

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_get_job_after_creation(self, client: TestClient) -> None:
        create_resp = client.post(
            "/jobs",
            data={"text": "Buscar status deste job."},
            headers=HEADERS,
        )
        job_id = create_resp.json()["job_id"]
        resp = client.get(f"/jobs/{job_id}", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["id"] == job_id
        assert data["status"] == "queued"


# ===================================================================
# 6. Jobs — GET /jobs/{job_id}/download
# ===================================================================

class TestDownloadAudio:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_download_not_found(self, client: TestClient) -> None:
        resp = client.get("/jobs/nonexistent/download", headers=HEADERS)
        assert resp.status_code == 404

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_download_not_ready_returns_425(
        self, client: TestClient, fake_job_store: FakeJobStore
    ) -> None:
        from app.domain.models import AudioGenerationJob
        job = AudioGenerationJob.create_new(text="Download test.")
        fake_job_store.save_job(job)
        resp = client.get(f"/jobs/{job.id}/download", headers=HEADERS)
        assert resp.status_code == 425


# ===================================================================
# 7. Jobs — DELETE /jobs/{job_id}
# ===================================================================

class TestDeleteJob:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_delete_job_not_found(self, client: TestClient) -> None:
        resp = client.delete("/jobs/nonexistent", headers=HEADERS)
        assert resp.status_code == 404

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_delete_job_success(self, client: TestClient) -> None:
        create_resp = client.post(
            "/jobs",
            data={"text": "Job para deletar."},
            headers=HEADERS,
        )
        job_id = create_resp.json()["job_id"]
        resp = client.delete(f"/jobs/{job_id}", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["job_id"] == job_id
        assert "deleted" in data["message"].lower() or "removed" in data["message"].lower()

        get_resp = client.get(f"/jobs/{job_id}", headers=HEADERS)
        assert get_resp.status_code == 404

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_delete_job_with_output_file(
        self, client: TestClient, fake_job_store: FakeJobStore, tmp_path
    ) -> None:
        from app.domain.models import AudioGenerationJob
        from app.domain.models import JobStatus
        job = AudioGenerationJob.create_new(text="Com output.")
        out_file = tmp_path / "test_output.wav"
        out_file.write_bytes(_make_wav_bytes())
        job.output_file = str(out_file)
        job.status = JobStatus.COMPLETED
        fake_job_store.save_job(job)

        resp = client.delete(f"/jobs/{job.id}", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["files_deleted"] >= 1


# ===================================================================
# 8. Voices — POST /voices
# ===================================================================

class TestCreateVoiceProfile:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_create_voice_valid(self, client: TestClient, fake_voice_store: FakeVoiceStore) -> None:
        from app.infrastructure import dependencies as deps
        fake_vm = FakeVoiceManager(fake_voice_store)
        deps.voice_manager.set(fake_vm)

        wav = _make_wav_bytes()
        resp = client.post(
            "/voices",
            data={"name": "Minha Voz", "description": "Voz de teste"},
            files={"file": ("test.wav", io.BytesIO(wav), "audio/wav")},
            headers=HEADERS,
        )
        data = _json_response(resp, 201)
        assert data["name"] == "Minha Voz"
        assert data["id"].startswith("vc_")
        assert data["status"] == "active"

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_create_voice_missing_name_returns_422(self, client: TestClient) -> None:
        wav = _make_wav_bytes()
        resp = client.post(
            "/voices",
            data={"description": "Sem nome."},
            files={"file": ("test.wav", io.BytesIO(wav), "audio/wav")},
            headers=HEADERS,
        )
        assert resp.status_code == 422

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_create_voice_missing_file_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/voices",
            data={"name": "Sem arquivo"},
            headers=HEADERS,
        )
        assert resp.status_code == 422


# ===================================================================
# 9. Voices — GET /voices
# ===================================================================

class TestListVoices:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_list_voices_empty(self, client: TestClient) -> None:
        resp = client.get("/voices", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["profiles"] == []
        assert data["total"] == 0

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_list_voices_after_creation(
        self, client: TestClient, fake_voice_store: FakeVoiceStore
    ) -> None:
        from app.domain.models import VoiceProfile
        from common.datetime_utils import now_brazil
        for i in range(3):
            fake_voice_store.save_profile(VoiceProfile(
                id=f"vc_voice{i}", name=f"Voz {i}",
                created_at=now_brazil(), audio_path=f"/tmp/v{i}.wav",
                duration_seconds=5.0, sample_rate=24000, status="active",
            ))
        resp = client.get("/voices", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["total"] == 3
        assert len(data["profiles"]) == 3


# ===================================================================
# 10. Voices — GET /voices/{voice_id}
# ===================================================================

class TestGetVoiceProfile:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_get_voice_not_found(self, client: TestClient) -> None:
        resp = client.get("/voices/nonexistent_voice", headers=HEADERS)
        assert resp.status_code == 404

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_get_voice_existing(
        self, client: TestClient, fake_voice_store: FakeVoiceStore
    ) -> None:
        from app.domain.models import VoiceProfile
        from common.datetime_utils import now_brazil
        vid = "vc_myvoice"
        fake_voice_store.save_profile(VoiceProfile(
            id=vid, name="Minha Voz", description="desc",
            created_at=now_brazil(), audio_path="/tmp/my.wav",
            duration_seconds=12.0, sample_rate=24000, status="active",
        ))
        resp = client.get(f"/voices/{vid}", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["id"] == vid
        assert data["name"] == "Minha Voz"


# ===================================================================
# 11. Voices — GET /voices/{voice_id}/sample
# ===================================================================

class TestDownloadVoiceSample:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_download_sample_not_found(self, client: TestClient) -> None:
        resp = client.get("/voices/nonexistent_voice/sample", headers=HEADERS)
        assert resp.status_code == 404

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_download_sample_existing(
        self, client: TestClient, fake_voice_store: FakeVoiceStore, tmp_path
    ) -> None:
        from app.domain.models import VoiceProfile
        from common.datetime_utils import now_brazil
        vid = "vc_sample_test"
        wav_file = tmp_path / f"{vid}.wav"
        wav_file.write_bytes(_make_wav_bytes())
        fake_voice_store.save_profile(VoiceProfile(
            id=vid, name="Sample Voice",
            created_at=now_brazil(), audio_path=str(wav_file),
            duration_seconds=10.0, sample_rate=24000, status="active",
        ))
        resp = client.get(f"/voices/{vid}/sample", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"


# ===================================================================
# 12. Voices — DELETE /voices/{voice_id}
# ===================================================================

class TestDeleteVoiceProfile:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_delete_voice_not_found(self, client: TestClient) -> None:
        resp = client.delete("/voices/nonexistent_voice", headers=HEADERS)
        assert resp.status_code == 404

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_delete_voice_success(
        self, client: TestClient, fake_voice_store: FakeVoiceStore
    ) -> None:
        from app.domain.models import VoiceProfile
        from common.datetime_utils import now_brazil
        vid = "vc_to_delete"
        fake_voice_store.save_profile(VoiceProfile(
            id=vid, name="Delete Me",
            created_at=now_brazil(), audio_path="/tmp/del.wav",
            duration_seconds=5.0, sample_rate=24000, status="active",
        ))
        resp = client.delete(f"/voices/{vid}", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["voice_id"] == vid
        assert fake_voice_store.get_profile(vid) is None


# ===================================================================
# 13. Admin — GET /admin/stats
# ===================================================================

class TestAdminStats:
    @pytest.mark.e2e
    @pytest.mark.admin
    def test_stats_empty(self, client: TestClient) -> None:
        resp = client.get("/admin/stats", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["service"] == "audio-generation"
        assert data["jobs"]["total"] == 0

    @pytest.mark.e2e
    @pytest.mark.admin
    def test_stats_after_jobs_created(self, client: TestClient) -> None:
        for txt in ["Job A", "Job B"]:
            client.post("/jobs", data={"text": txt}, headers=HEADERS)
        resp = client.get("/admin/stats", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["jobs"]["total"] == 2
        assert "queued" in data["jobs"]["by_status"]


# ===================================================================
# 14. Admin — POST /admin/cleanup
# ===================================================================

class TestAdminCleanup:
    @pytest.mark.e2e
    @pytest.mark.admin
    def test_cleanup_removes_completed_and_failed(
        self, client: TestClient, fake_job_store: FakeJobStore
    ) -> None:
        from app.domain.models import AudioGenerationJob, JobStatus
        from datetime import datetime

        j1 = AudioGenerationJob.create_new(text="Done job")
        j1.status = JobStatus.COMPLETED
        j1.completed_at = datetime.now()
        fake_job_store.save_job(j1)

        j2 = AudioGenerationJob.create_new(text="Failed job")
        j2.status = JobStatus.FAILED
        j2.error_message = "test error"
        fake_job_store.save_job(j2)

        j3 = AudioGenerationJob.create_new(text="Active job")
        fake_job_store.save_job(j3)

        resp = client.post("/admin/cleanup", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["jobs_removed"] == 2
        assert fake_job_store.get_job(j3.id) is not None

    @pytest.mark.e2e
    @pytest.mark.admin
    def test_cleanup_no_jobs(self, client: TestClient) -> None:
        resp = client.post("/admin/cleanup", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["jobs_removed"] == 0


# ===================================================================
# 15. Authentication tests
# ===================================================================

class TestAuthentication:
    @pytest.mark.e2e
    @pytest.mark.auth
    def test_valid_api_key_accepted(self, client: TestClient) -> None:
        resp = client.get("/jobs", headers=HEADERS)
        assert resp.status_code == 200

    @pytest.mark.e2e
    @pytest.mark.auth
    def test_exempt_paths_need_no_key(self, client: TestClient) -> None:
        for path in ("/", "/health"):
            resp = client.get(path)
            assert resp.status_code == 200
