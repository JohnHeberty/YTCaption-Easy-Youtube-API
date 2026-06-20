"""Tests for Audio Generation Service — unit tests only (no model required)."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.domain.models import AudioGenerationJob, VoiceProfile
from app.services.audio_utils import chunk_text, validate_voice_sample
from app.services.generator import TTSGenerator
from app.services.model_manager import ChatterboxModelManager


class MockModelManager:
    def __init__(self):
        self._loaded = False

    @property
    def is_loaded(self):
        return self._loaded

    @property
    def device(self):
        return "cpu"

    @property
    def sample_rate(self):
        return 24000

    def load_model(self):
        self._loaded = True

    def unload_model(self):
        self._loaded = False

    def generate(self, text, audio_prompt_path=None,
                 exaggeration=0.5, temperature=0.8, cfg_weight=0.5):
        import torch
        duration_samples = int(self.sample_rate * max(1.0, len(text) / 20))
        t = torch.linspace(0, 2 * 3.14159 * 440 * duration_samples / self.sample_rate, duration_samples)
        wave = torch.sin(t) * 0.3 + torch.randn(duration_samples) * 0.05
        return wave.unsqueeze(0)

    def get_status(self):
        return {"loaded": self._loaded, "device": "cpu", "model": "mock"}


class MockJobStore:
    def __init__(self):
        self._jobs = {}

    def save_job(self, job):
        self._jobs[job.id] = job

    def get_job(self, job_id):
        return self._jobs.get(job_id)

    def update_job(self, job):
        self._jobs[job.id] = job

    def list_jobs(self, limit=20):
        return list(self._jobs.values())[:limit]

    def delete_job(self, job_id):
        return self._jobs.pop(job_id, None) is not None


class MockVoiceStore:
    def __init__(self):
        self._profiles = {}

    def save_profile(self, profile):
        self._profiles[profile.id] = profile

    def get_profile(self, voice_id):
        return self._profiles.get(voice_id)

    def list_profiles(self):
        return list(self._profiles.values())

    def delete_profile(self, voice_id):
        return self._profiles.pop(voice_id, None) is not None


@pytest.fixture
def model_manager():
    return MockModelManager()


@pytest.fixture
def job_store():
    return MockJobStore()


@pytest.fixture
def voice_store():
    return MockVoiceStore()


@pytest.fixture
def output_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def generator(model_manager, job_store, output_dir):
    return TTSGenerator(
        model_manager=model_manager,
        job_store=job_store,
        output_dir=output_dir,
        max_text_length=5000,
        chunk_size=1000,
    )


# ===== Audio Utils Tests =====


class TestChunkText:
    def test_short_text_single_chunk(self):
        text = "Hello world. This is a test."
        chunks = chunk_text(text, chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_multiple_chunks(self):
        text = "A. " * 200
        chunks = chunk_text(text, chunk_size=1000)
        assert len(chunks) > 1

    def test_paragraphs_preserved(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunk_text(text, chunk_size=1000)
        assert len(chunks) == 3

    def test_empty_text(self):
        assert chunk_text("", 250) == []


class TestValidateVoiceSample:
    def test_invalid_format(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"not audio")
        try:
            with pytest.raises(Exception):
                validate_voice_sample(f.name)
        finally:
            os.unlink(f.name)

    def test_file_not_found(self):
        with pytest.raises(Exception):
            validate_voice_sample("/nonexistent/file.wav")


# ===== Generator Tests (with mock model) =====


class TestTTSGenerator:
    def test_simple_generation(self, generator, job_store):
        job = AudioGenerationJob.create_new(text="Ola mundo, este e um teste.")
        job_store.save_job(job)
        result = generator.generate(job)
        assert result.status.value == "completed"
        assert result.output_file is not None
        assert Path(result.output_file).exists()
        assert result.output_duration_seconds > 0
        assert result.progress == 100.0

    def test_generation_with_voice_cloning(self, generator, job_store, output_dir):
        job = AudioGenerationJob.create_new(
            text="Teste com clonagem de voz.",
            voice_id="vc_test123",
        )
        job_store.save_job(job)
        audio_path = os.path.join(output_dir, "voice_ref.wav")
        import soundfile as sf
        import numpy as np
        sf.write(audio_path, np.zeros(24000 * 3), 24000)
        result = generator.generate(job, audio_prompt_path=audio_path)
        assert result.status.value == "completed"

    def test_empty_text_validation(self, generator, job_store):
        job = AudioGenerationJob.create_new(text="")
        job_store.save_job(job)
        with pytest.raises(Exception):
            generator.generate(job)
        assert job.status.value == "failed"

    def test_long_text_validation(self, generator, job_store):
        job = AudioGenerationJob.create_new(text="x" * 6000)
        job_store.save_job(job)
        with pytest.raises(Exception):
            generator.generate(job)
        assert job.status.value == "failed"

    def test_stages_tracking(self, generator, job_store):
        job = AudioGenerationJob.create_new(text="Test stage tracking.")
        job_store.save_job(job)
        result = generator.generate(job)
        assert "model_loading" in result.stages
        assert "text_chunking" in result.stages
        assert "audio_generation" in result.stages
        assert "audio_assembly" in result.stages

    def test_chunking_generation(self, generator, job_store):
        text = "Primeiro paragrafo.\n\nSegundo paragrafo com mais texto para testar.\n\nTerceiro paragrafo final."
        job = AudioGenerationJob.create_new(text=text)
        job_store.save_job(job)
        result = generator.generate(job)
        assert result.status.value == "completed"
        assert result.output_duration_seconds > 0


# ===== Model Manager Tests =====


class TestChatterboxModelManager:
    def test_init(self):
        mm = ChatterboxModelManager(device="cpu")
        assert mm.device == "cpu"
        assert not mm.is_loaded
        assert mm.sample_rate == 24000

    def test_get_status_not_loaded(self):
        mm = ChatterboxModelManager(device="cpu")
        status = mm.get_status()
        assert status["loaded"] is False
        assert status["device"] == "cpu"


# ===== API Tests (with mocked dependencies) =====


@pytest.fixture
def api_app(model_manager, job_store, voice_store, output_dir):
    mock_task_module = MagicMock()
    mock_task_module.generate_audio_task.apply_async = MagicMock(
        return_value=MagicMock(id="mock-task-id")
    )
    with patch("app.infrastructure.dependencies.get_model_manager", return_value=model_manager), \
         patch("app.infrastructure.dependencies.get_job_store", return_value=job_store), \
         patch("app.infrastructure.dependencies.get_voice_store", return_value=voice_store), \
         patch("app.infrastructure.dependencies.get_generator", return_value=TTSGenerator(
             model_manager, job_store, output_dir, 5000, 250
         )), \
         patch.dict("sys.modules", {"app.infrastructure.celery_tasks": mock_task_module}):
        from app.main import app as _app
        yield _app


@pytest.fixture
def client(api_app):
    return TestClient(api_app)


class TestAPI:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "audio-generation"

    def test_create_job(self, client):
        resp = client.post("/jobs", data={"text": "Teste de geracao de audio."})
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True
        assert data["job_id"].startswith("ag_")

    def test_create_job_with_voice_nonexistent(self, client):
        resp = client.post("/jobs", data={
            "text": "Teste com clonagem.",
            "voice_id": "vc_nonexistent",
        })
        assert resp.status_code == 404

    def test_get_job(self, client):
        create = client.post("/jobs", data={"text": "Test job."})
        job_id = create.json()["job_id"]
        resp = client.get(f"/jobs/{job_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == job_id

    def test_get_nonexistent_job(self, client):
        resp = client.get("/jobs/nonexistent")
        assert resp.status_code == 404

    def test_list_jobs(self, client):
        client.post("/jobs", data={"text": "Job 1."})
        client.post("/jobs", data={"text": "Job 2."})
        resp = client.get("/jobs")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 0

    def test_create_voice_empty_file(self, client):
        resp = client.post("/voices", data={"name": "Test"}, files={"file": ("empty.wav", b"", "audio/wav")})
        assert resp.status_code in (400, 422)

    def test_list_voices(self, client):
        resp = client.get("/voices")
        assert resp.status_code == 200
        assert "profiles" in resp.json()

    def test_voice_crud(self, client):
        import soundfile as sf
        import numpy as np
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, np.zeros(24000 * 8), 24000)
            with open(f.name, "rb") as audio:
                create = client.post("/voices", data={"name": "Test Voice"},
                                     files={"file": ("sample.wav", audio, "audio/wav")})
            os.unlink(f.name)
        assert create.status_code == 201
        voice_id = create.json()["id"]
        assert voice_id.startswith("vc_")

        get_resp = client.get(f"/voices/{voice_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Test Voice"

        delete = client.delete(f"/voices/{voice_id}")
        assert delete.status_code == 200

    def test_download_audio_not_ready(self, client):
        create = client.post("/jobs", data={"text": "Not ready."})
        job_id = create.json()["job_id"]
        resp = client.get(f"/jobs/{job_id}/download")
        assert resp.status_code == 425
