"""Shared fixtures for pipeline integration tests."""
import struct
import wave
from pathlib import Path

import pytest


def _generate_wav_bytes(duration_seconds: float = 10, sample_rate: int = 16000) -> bytes:
    """Generate a minimal valid WAV file as raw bytes.

    Produces a mono PCM 16-bit sine-wave-like signal (alternating samples).
    Suitable for pydub AudioSegment.from_file() and ffmpeg processing.
    """
    num_samples = int(duration_seconds * sample_rate)
    buf = bytearray()
    for i in range(num_samples):
        value = ((i % 256) - 128) << 8
        buf.extend(struct.pack('<h', value))

    with wave.open(_ := __import__('io').BytesIO(), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(buf))
        return _getvalue()


def _generate_wav_bytes(duration_seconds: float = 10, sample_rate: int = 16000) -> bytes:
    """Generate a minimal valid WAV file as raw bytes."""
    import io
    num_samples = int(duration_seconds * sample_rate)
    buf = bytearray()
    for i in range(num_samples):
        value = ((i % 256) - 128) << 8
        buf.extend(struct.pack('<h', value))

    bio = io.BytesIO()
    with wave.open(bio, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(buf))
    return bio.getvalue()


def _generate_long_wav_bytes(duration_seconds: float = 65, sample_rate: int = 16000) -> bytes:
    """Generate a longer WAV file (> chunk threshold for multi-chunk testing)."""
    import io
    num_samples = int(duration_seconds * sample_rate)
    buf = bytearray()
    for i in range(num_samples):
        value = ((i % 256) - 128) << 8
        buf.extend(struct.pack('<h', value))

    bio = io.BytesIO()
    with wave.open(bio, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(buf))
    return bio.getvalue()


@pytest.fixture
def sample_wav_bytes():
    """Raw bytes of a minimal valid WAV file (10 s, 16 kHz mono)."""
    return _generate_wav_bytes(duration_seconds=10, sample_rate=16000)


@pytest.fixture
def long_sample_wav_bytes():
    """Raw bytes of a longer WAV file (65 s, 16 kHz mono) for multi-chunk tests."""
    return _generate_long_wav_bytes(duration_seconds=65, sample_rate=16000)


@pytest.fixture
def mock_transcriber_engine():
    """Mock ITranscriber that returns deterministic segments and text per chunk.

    The transcribe_fn callable signature expected by ChunkTranscriber is:
        (chunk_path: str, lang_in: str, lang_out: Optional[str]) -> dict with 'text' and 'segments'.
    """
    call_count = 0

    def transcribe_fn(chunk_path: str, language_in: str, language_out=None):
        nonlocal call_count
        call_count += 1
        chunk_id = call_count
        return {
            "text": f"Transcribed text for chunk {chunk_id}",
            "segments": [
                {
                    "start": float(chunk_id - 1) * 5,
                    "end": float(chunk_id) * 5,
                    "text": f"This is segment from chunk {chunk_id}",
                }
            ],
        }

    transcribe_fn.call_count = call_count  # type: ignore[attr-defined]
    return transcribe_fn


@pytest.fixture
def mock_transcriber_engine_with_overlap():
    """Mock engine that returns overlapping text to exercise merge logic."""
    call_count = 0

    def transcribe_fn(chunk_path: str, language_in: str, language_out=None):
        nonlocal call_count
        call_count += 1
        chunk_id = call_count
        # Return two segments per chunk with some overlap between chunks
        return {
            "text": f"Transcribed text for chunk {chunk_id}",
            "segments": [
                {
                    "start": float(chunk_id - 1) * 28,
                    "end": float(chunk_id - 1) * 28 + 30,
                    "text": f"This is segment from chunk {chunk_id} part one",
                },
                {
                    # Overlapping region — same text as end of previous chunk would produce
                    "start": float(chunk_id - 1) * 28 + 29,
                    "end": float(chunk_id - 1) * 28 + 30,
                    "text": f"This is segment from chunk {chunk_id} overlap",
                },
            ],
        }

    transcribe_fn.call_count = call_count  # type: ignore[attr-defined]
    return transcribe_fn


@pytest.fixture
def mock_transcriber_engine_failing():
    """Mock engine that raises on the second call to test failure paths."""
    call_count = 0

    def transcribe_fn(chunk_path: str, language_in: str, language_out=None):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Simulated transcription engine failure")
        return {
            "text": f"Transcribed text for chunk {call_count}",
            "segments": [
                {"start": float(call_count - 1) * 5, "end": float(call_count) * 5, "text": f"Segment {call_count}"}
            ],
        }

    transcribe_fn.call_count = call_count  # type: ignore[attr-defined]
    return transcribe_fn


@pytest.fixture
def mock_job_store_fakeredis():
    """Real RedisJobStore backed by fakeredis (not MagicMock)."""
    import fakeredis

    # Patch ResilientRedisStore *before* importing RedisJobStore so that the
    # __init__ connection test uses our fake client instead of hitting the network.
    from unittest.mock import patch, MagicMock

    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    mock_resilient = MagicMock()
    mock_resilient.redis = fake_redis

    with patch(
        "app.infrastructure.redis_store.ResilientRedisStore",
        return_value=mock_resilient,
    ):
        from app.infrastructure.redis_store import RedisJobStore

        store = RedisJobStore(redis_url="redis://fake:6379/0")

    # Ensure the store's internal clients point to fakeredis.
    # _resilient.redis is used by __init__, but _raw_redis property reads self.redis.redis,
    # and save_job/get_job use self._redis_client directly (set from self._resilient.redis).
    store._resilient = mock_resilient
    store._redis_client = fake_redis
    return store


@pytest.fixture
def mock_job_store_inmemory():
    """Simple in-memory job store implementing IJobStore for tests that don't need Redis."""

    class InMemoryJobStore:
        def __init__(self):
            self._store = {}
            self.redis = None  # placeholder — not used by these tests

        def save_job(self, job):
            if hasattr(job, "updated_at"):
                from datetime import datetime, timezone
                job.updated_at = datetime.now(timezone.utc)
            self._store[job.id] = job.model_copy(deep=True)
            return job

        def get_job(self, job_id: str):
            entry = self._store.get(job_id)
            if entry is None:
                return None
            from app.domain.models import AudioTranscriptionJob
            return AudioTranscriptionJob(**entry.model_dump())

        def update_job(self, job):
            return self.save_job(job)

        def delete_job(self, job_id: str) -> bool:
            if job_id in self._store:
                del self._store[job_id]
                return True
            return False

        def list_jobs(self, limit=100, status=None, offset=0):
            jobs = []
            for jid in reversed(list(self._store.keys())):
                job = self.get_job(jid)
                if job is None:
                    continue
                if status is not None and str(job.status) != str(status):
                    continue
                jobs.append(job)
            return jobs[offset: offset + limit]

        def get_stats(self):
            total = len(self._store)
            by_status = {}
            for jid in self._store.keys():
                job = self.get_job(jid)
                if job:
                    s = str(job.status)
                    by_status[s] = by_status.get(s, 0) + 1
            return {"total_jobs": total, "by_status": by_status}

        async def find_orphaned_jobs(self, max_age_minutes=30):
            from datetime import timedelta
            now_brazil_fn = None
            try:
                from common.datetime_utils import now_brazil as nb
                now_brazil_fn = nb
            except ImportError:
                pass
            if now_brazil_fn is None:
                return []

            orphaned = []
            threshold = timedelta(minutes=max_age_minutes)
            for job in self.list_jobs(limit=5000):
                from app.domain.models import JobStatus as DS
                if str(job.status) not in ("processing", "queued"):
                    continue
                ref_time = getattr(job, 'started_at', None) or getattr(job, 'updated_at', None) or getattr(job, 'created_at', None)
                if ref_time and (now_brazil_fn() - ref_time).total_seconds() > threshold.total_seconds():
                    orphaned.append(job)
            return orphaned

        async def get_queue_info(self):
            from common.datetime_utils import now_brazil as nb
            try:
                ts = nb().isoformat()
            except ImportError:
                ts = "now"
            return {"queue_name": "test", "pending_jobs": 0, "timestamp": ts}

    return InMemoryJobStore()


@pytest.fixture
def sample_job():
    """Create a QUEUED AudioTranscriptionJob for testing."""
    from app.domain.models import Job, WhisperEngine
    try:
        from common.datetime_utils import now_brazil as nb_fn
    except ImportError:
        from datetime import datetime, timezone

        def nb_fn():
            return datetime.now(timezone.utc)

    from datetime import timedelta

    fixed = nb_fn()
    job = Job(
        id="integration_test_job_001",
        input_file="/tmp/test_input.wav",
        status="queued",
        operation="transcribe",
        language_in="pt",
        engine=WhisperEngine.FASTER_WHISPER,
        filename="test_input.wav",
        file_size_input=320_000,
        received_at=fixed,
        created_at=fixed,
        expires_at=fixed + timedelta(hours=24),
    )
    return job


@pytest.fixture
def temp_pipeline_dirs(tmp_path):
    """Temp directories for pipeline integration tests."""
    upload = tmp_path / "uploads"
    output = tmp_path / "output"
    models_dir = tmp_path / "models"

    upload.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    return {
        "upload": upload,
        "output": output,
        "temp": tmp_path / "temp",
        "models": models_dir,
    }


@pytest.fixture(autouse=True)
def _mock_now_brazil(monkeypatch):
    """Pin now_brazil() to a fixed datetime for deterministic tests."""
    from datetime import datetime, timezone

    fixed = datetime(2025, 6, 14, 12, 0, 0, tzinfo=timezone.utc)

    def mock_now():
        return fixed

    try:
        monkeypatch.setattr("common.datetime_utils.now_brazil", mock_now)
    except Exception:
        pass


def _srt_format_segment(index: int, start_s: float, end_s: float, text: str) -> str:
    """Format a single SRT segment string."""

    def _fmt(s):
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:06.3f}"

    start_str = _fmt(start_s).replace('.', ',')
    end_str = _fmt(end_s).replace('.', ',')
    return f"{index}\n{start_str} --> {end_str}\n{text}\n"


def segments_to_srt(segments: list[dict]) -> str:
    """Convert a list of segment dicts to SRT caption format."""
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(_srt_format_segment(i, float(seg["start"]), float(seg["end"]), seg["text"]))
    return "\n".join(lines)
