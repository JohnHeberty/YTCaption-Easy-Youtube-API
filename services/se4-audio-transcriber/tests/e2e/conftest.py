"""
Shared fixtures for E2E job lifecycle tests.

Uses FastAPI TestClient with DI overrides to simulate full upload → poll → download flow
without requiring real Redis, Celery workers, or Whisper models.
"""
import io
import wave
import struct
from datetime import datetime, timezone, timedelta as td
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _generate_wav_bytes(duration_seconds: float = 10.0) -> bytes:
    """Generate minimal valid WAV audio file in memory."""
    sample_rate = 16000
    num_samples = int(sample_rate * duration_seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for _ in range(num_samples):
            buf.write(struct.pack("<h", 0))
    return buf.getvalue()


def generate_wav_bytes(duration_seconds=5.0):
    """Alias used by test files."""
    return _generate_wav_bytes(duration_seconds)


class MockE2EJobStore:
    """In-memory job store that simulates state transitions for E2E polling tests."""

    def __init__(self):
        self._jobs = {}
        self._poll_count = 0

    async def start_cleanup_task(self):
        pass

    async def stop_cleanup_task(self):
        pass

    def get_job(self, job_id: str):
        return self._jobs.get(job_id)

    def save_job(self, job):
        jid = getattr(job, "id", None) or (job.get("id") if isinstance(job, dict) else None)
        if jid:
            self._jobs[jid] = job

    def update_job(self, job):
        jid = getattr(job, "id", None) or (job.get("id") if isinstance(job, dict) else None)
        if jid:
            self._jobs[jid] = job

    def delete_job(self, job_id: str):
        self._jobs.pop(job_id, None)

    def list_jobs(self, limit=20):
        jobs = list(self._jobs.values())[-limit:]
        return sorted(jobs, key=lambda j: getattr(j, "created_at", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)

    def get_stats(self):
        from collections import Counter
        statuses = Counter(getattr(j, "status", None) for j in self._jobs.values())
        return {"total_jobs": len(self._jobs), "by_status": dict(statuses)}

    async def find_orphaned_jobs(self, max_age_minutes=30):
        cutoff = datetime.now(timezone.utc) - td(minutes=max_age_minutes)
        orphaned = []
        for j in self._jobs.values():
            if getattr(j, "status", None) and str(getattr(j.status, "value", "")) == "processing":
                started = getattr(j, "started_at", None) or getattr(j, "updated_at", cutoff - td(hours=1))
                if isinstance(started, datetime):
                    orphaned.append(j)
        return orphaned

    async def get_queue_info(self):
        from collections import Counter
        statuses = Counter(getattr(j, "status", None) for j in self._jobs.values())
        queued_count = 0
        processing_count = 0
        for s, c in statuses.items():
            sv = str(getattr(s, "value", "")) if hasattr(s, "value") else str(s).lower()
            if "queued" in sv:
                queued_count += c
            elif "processing" in sv:
                processing_count += c
        return {"queued": queued_count, "processing": processing_count}

    @property
    def redis(self):
        r = MagicMock()
        r.ping.return_value = True
        return r


class StateTransitionJobStore(MockE2EJobStore):
    """Specialized store that evolves job status on each poll for E2E testing."""

    STATES = ["queued", "processing", "completed"]

    def get_job(self, job_id: str):
        self._poll_count += 1
        job = super().get_job(job_id)
        if job is None or not hasattr(job, "status"):
            return job
        from app.domain.models import JobStatus
        current_idx = 0
        try:
            sv = getattr(getattr(job, "status", None), "value", str(job.status))
            current_idx = self.STATES.index(sv) if sv in self.STATES else 0
        except (ValueError, AttributeError):
            pass

        target_idx = min(current_idx + max(1, self._poll_count - 2), len(self.STATES) - 1)
        new_status_str = self.STATES[target_idx]

        if hasattr(job.status, "value") and job.status.value != new_status_str:
            try:
                # Use model_copy to avoid mutating frozen Pydantic models in place
                updated_data = {"status": JobStatus(new_status_str.upper())}
                now_bz = datetime.now(timezone.utc) - td(hours=3)
                if target_idx == len(self.STATES) - 1:
                    updated_data["completed_at"] = now_bz

                # Try model_copy first (Pydantic v2), fall back to direct mutation
                try:
                    job = job.model_copy(update=updated_data, deep=True)
                except AttributeError:
                    for k, v in updated_data.items():
                        setattr(job, k, v)

            except (ValueError, TypeError):
                pass

        self.update_job(job)
        return job


@pytest.fixture()
def mock_e2e_store():
    """Basic in-memory store for E2E tests."""
    return MockE2EJobStore()


@pytest.fixture()
def state_transition_store():
    """Store that evolves status on each poll (queued → processing → completed)."""
    return StateTransitionJobStore()


@pytest.fixture()
def wav_audio_file(tmp_path):
    """Create a temporary WAV file for upload testing."""
    p = tmp_path / "test_audio.wav"
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        for _ in range(int(16000 * 5)):
            buf.write(struct.pack("<h", 0))
    p.write_bytes(buf.getvalue())
    return p


@pytest.fixture()
def wav_audio_content():
    """Raw WAV bytes for multipart upload."""
    return generate_wav_bytes(5.0)
