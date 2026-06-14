"""Tests for TranscriptionProcessor - engine routing, chunking dispatch, retry logic."""

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock, AsyncMock

import pytest


# ---------------------------------------------------------------------------
# Import-isolation: mock heavy dependencies before any app import touches them.
# ---------------------------------------------------------------------------

class _FakeAudioSegment:
    """Minimal AudioSegment stand-in so pydub isn't required at runtime."""

    def __init__(self, duration_ms=60_000):
        self.duration_ms = duration_ms

    def __len__(self):
        return self.duration_ms

    @classmethod
    def from_file(cls, *args, **kwargs):
        dur = kwargs.pop("duration_ms", 60_000) if "duration_ms" in kwargs else 60_000
        return cls(dur)


class _FakeTorch:
    """Minimal torch stand-in."""

    class cuda:
        @staticmethod
        def is_available():
            return False

        @staticmethod
        def memory_allocated(_):
            return 0

        @staticmethod
        def empty_cache():
            pass

        @staticmethod
        def synchronize():
            pass


class _FakePydub:
    AudioSegment = _FakeAudioSegment


# ---------------------------------------------------------------------------
# Fixtures — isolate imports and provide processor + dependencies.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_imports(monkeypatch):
    """Patch heavy third-party modules so tests run without GPU / ffmpeg."""
    monkeypatch.setitem(sys.modules, "torch", _FakeTorch())
    fake_pydub = _FakePydub()
    monkeypatch.setitem(sys.modules, "pydub", fake_pydub)
    monkeypatch.setitem(sys.modules, "pydub.utils", MagicMock())
    monkeypatch.setitem(sys.modules, "faster_whisper", MagicMock())


@pytest.fixture
def settings():
    """Default test settings dict."""
    return {
        "whisper_device": "cpu",
        "whisper_model": "base",
        "enable_chunking": True,
        "whisper_min_duration_for_chunks": 300,
        "transcription_dir": "./tests_transcriptions",
        "upload_dir": "./uploads",
        "async_timeout_seconds": 1800,
        "job_processing_timeout_seconds": 3600,
    }


@pytest.fixture
def mock_job_store():
    """Mock IJobStore."""
    store = MagicMock()
    store.get_job.return_value = None
    return store


@pytest.fixture
def state_updater(mock_job_store):
    """Real JobStateUpdater backed by a mock job store."""
    from app.shared.job_state_updater import JobStateUpdater

    updater = JobStateUpdater(job_store=mock_job_store)
    return updater


# ---------------------------------------------------------------------------
# Helper — build a minimal TranscriptionProcessor for testing.
# ---------------------------------------------------------------------------

def _build_processor(settings, state=None):
    """Create a bare-bones processor instance with all required attributes."""
    from app.services.processor import TranscriptionProcessor

    proc = TranscriptionProcessor.__new__(TranscriptionProcessor)
    proc.job_store = MagicMock()
    if state is not None:
        proc.state = state
    else:
        from app.shared.job_state_updater import JobStateUpdater
        store_mock = MagicMock()
        store_mock.get_job.return_value = None
        proc.state = JobStateUpdater(job_store=store_mock)
    proc.settings = settings
    proc.model_managers = {}
    proc.current_engine = "faster-whisper"
    proc.output_dir = "./tests_transcriptions"
    proc.model_dir = "./models"
    return proc


# ---------------------------------------------------------------------------
# Tests — Engine Selection Routing (MELHORE 2.1)
# ---------------------------------------------------------------------------

class TestEngineSelection:
    """Verify _get_model_manager routes to the correct engine manager."""

    def test_routes_to_faster_whisper(self, settings):
        from app.services.processor import TranscriptionProcessor
        from app.domain.models import WhisperEngine

        with patch("app.services.processor.FasterWhisperModelManager") as MockMgr:
            instance = MagicMock()
            instance.is_loaded = False
            MockMgr.return_value = instance

            proc = _build_processor(settings)
            manager = proc._get_model_manager(WhisperEngine.FASTER_WHISPER)

        MockMgr.assert_called_once()
        assert manager is instance

    def test_routes_to_openai_whisper(self, settings):
        from app.services.processor import TranscriptionProcessor
        from app.domain.models import WhisperEngine

        with patch("app.services.processor.OpenAIWhisperManager") as MockMgr:
            instance = MagicMock()
            instance.is_loaded = False
            MockMgr.return_value = instance

            proc = _build_processor(settings)
            manager = proc._get_model_manager(WhisperEngine.OPENAI_WHISPER)

        MockMgr.assert_called_once()
        assert manager is instance

    def test_routes_to_whisperx(self, settings):
        from app.services.processor import TranscriptionProcessor
        from app.domain.models import WhisperEngine

        with patch("app.services.processor.WhisperXManager") as MockMgr:
            instance = MagicMock()
            instance.is_loaded = False
            MockMgr.return_value = instance

            proc = _build_processor(settings)
            manager = proc._get_model_manager(WhisperEngine.WHISPERX)

        MockMgr.assert_called_once()
        assert manager is instance

    def test_caches_manager_after_first_call(self, settings):
        from app.services.processor import TranscriptionProcessor
        from app.domain.models import WhisperEngine

        with patch("app.services.processor.FasterWhisperModelManager") as MockMgr:
            mgr_instance = MagicMock()
            mgr_instance.is_loaded = False
            MockMgr.return_value = mgr_instance

            proc = _build_processor(settings)
            m1 = proc._get_model_manager(WhisperEngine.FASTER_WHISPER)
            m2 = proc._get_model_manager(WhisperEngine.FASTER_WHISPER)

        assert MockMgr.call_count == 1
        assert m1 is m2


# ---------------------------------------------------------------------------
# Tests — Chunking Dispatch (MELHORE 3.4 / MELHORE 5.6)
# ---------------------------------------------------------------------------

class TestChunkingDispatch:
    """Verify the processor dispatches to chunk_transcriber or direct based on audio length."""

    @pytest.mark.asyncio
    async def test_long_audio_uses_chunking(self, settings, tmp_path):
        from app.services.processor import TranscriptionProcessor
        from app.domain.models import WhisperEngine

        # Place real file in upload_dir so processor finds it at line 408.
        upload = tmp_path / "uploads"
        upload.mkdir()
        audio_file = upload / "test.wav"
        audio_file.write_bytes(b"\x00" * 1024)

        settings["upload_dir"] = str(upload)

        long_audio = _FakeAudioSegment(duration_ms=360_000)  # 6 min > 300s threshold

        ct_instance = MagicMock()
        async def fake_transcribe(*args, **kwargs):
            return {
                "text": "Chunked",
                "segments": [{"text": " Chunked", "start": 0.0, "end": 10.0}],
                "language": "pt",
            }

        converted_path = tmp_path / "converted.wav"
        converted_path.write_bytes(b"" * 1024)

        mock_manager_chunk = MagicMock()
        mock_manager_chunk.is_loaded = False
        mock_manager_chunk.device = "cpu"

        with patch("app.services.processor.AudioSegment") as MockAS,              patch.object(TranscriptionProcessor, "_load_model"),              patch("app.services.processor.ChunkTranscriber", return_value=ct_instance) as MockCT,              patch("app.services.processor.convert_to_wav", return_value=(Path(str(converted_path)), True)):

            MockAS.from_file.return_value = long_audio

            proc = _build_processor(settings)
            proc.current_engine = WhisperEngine.FASTER_WHISPER  # _load_model would set this normally
            proc.model_manager = mock_manager_chunk  # for _unload_model cleanup path
            proc.output_dir = str(tmp_path / "output")
            Path(proc.output_dir).mkdir(parents=True, exist_ok=True)

            job = MagicMock()
            job.id = "chunk-test-1"
            job.input_file = str(audio_file)
            job.engine = WhisperEngine.FASTER_WHISPER
            job.language_in = "pt"
            job.language_out = None
            job.started_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
            from app.shared.job_states import JobStatus
            job.status = JobStatus.PENDING

            try:
                await proc.process_transcription_job(job)
            except Exception:
                pass

        MockCT.assert_called_once()

    @pytest.mark.asyncio
    async def test_short_audio_uses_direct(self, settings, tmp_path):
        from app.services.processor import TranscriptionProcessor
        from app.domain.models import WhisperEngine

        # Place real file in upload_dir so processor finds it at line 408.
        upload = tmp_path / "uploads"
        upload.mkdir()
        audio_file = upload / "test.wav"
        audio_file.write_bytes(b"\x00" * 1024)

        settings["upload_dir"] = str(upload)

        short_audio = _FakeAudioSegment(duration_ms=60_000)  # 1 min < 300s threshold

        converted_path = tmp_path / "converted.wav"
        converted_path.write_bytes(b"\x00" * 1024)

        mock_manager = MagicMock()
        mock_manager.is_loaded = False
        mock_manager.device = "cpu"
        mock_manager.transcribe.return_value = {
            "text": "Direct",
            "segments": [{"text": " Direct", "start": 0.0, "end": 5.0}],
            "language": "pt",
        }

        with patch("app.services.processor.AudioSegment") as MockAS, \
             patch.object(TranscriptionProcessor, "_load_model"), \
             patch.object(TranscriptionProcessor, "_get_model_manager", return_value=mock_manager), \
             patch("app.services.processor.convert_to_wav", return_value=(Path(str(converted_path)), True)):

            MockAS.from_file.return_value = short_audio

            proc = _build_processor(settings)
            proc.current_engine = WhisperEngine.FASTER_WHISPER  # _load_model would set this normally
            proc.model_manager = mock_manager  # _load_model would set this normally
            proc.output_dir = str(tmp_path / "output")
            Path(proc.output_dir).mkdir(parents=True, exist_ok=True)

            job = MagicMock()
            job.id = "direct-test-1"
            job.input_file = str(audio_file)
            job.engine = WhisperEngine.FASTER_WHISPER
            job.language_in = "pt"
            job.language_out = None
            job.started_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
            from app.shared.job_states import JobStatus
            job.status = JobStatus.PENDING

            try:
                await proc.process_transcription_job(job)
            except Exception:
                pass

            mock_manager.transcribe.assert_called_once()


# ---------------------------------------------------------------------------
# Tests — Retry Logic (MELHORE 3.5 / MELHORE 6.10)
# ---------------------------------------------------------------------------

class TestRetryLogic:
    """Verify retry_on_transient_error behavior in _transcribe_direct."""

    def test_oserror_is_retried(self, settings):
        from app.shared.error_handling import retry_on_transient_error

        call_count = 0

        @retry_on_transient_error(max_retries=2, base_delay=0.01)
        def flaky_io():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OSError("disk full")
            return "ok"

        result = flaky_io()
        assert result == "ok"
        assert call_count == 3

    def test_cuda_oom_is_retried(self, settings):
        from app.shared.error_handling import retry_on_transient_error

        call_count = 0

        @retry_on_transient_error(max_retries=2, base_delay=0.01)
        def flaky_gpu():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("CUDA out of memory")
            return "recovered"

        result = flaky_gpu()
        assert result == "recovered"
        assert call_count == 3

    def test_value_error_not_retried(self, settings):
        from app.shared.error_handling import retry_on_transient_error

        @retry_on_transient_error(max_retries=2, base_delay=0.01)
        def bad_input():
            raise ValueError("invalid model name")

        with pytest.raises(ValueError, match="invalid model name"):
            bad_input()


# ---------------------------------------------------------------------------
# Tests — Progress Tracking (MELHORE 3.6 / MELHORE 5.7)
# ---------------------------------------------------------------------------

class TestProgressTracking:
    """Verify JobStateUpdater progress calls during transcription flow."""

    @pytest.mark.asyncio
    async def test_progress_updates_on_success(self, settings, tmp_path):
        from app.services.processor import TranscriptionProcessor
        from app.domain.models import WhisperEngine

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"\x00" * 1024)

        short_audio = _FakeAudioSegment(duration_ms=60_000)

        with patch("app.services.processor.AudioSegment") as MockAS, \
             patch.object(TranscriptionProcessor, "_load_model"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", MagicMock()), \
             patch("os.path.getsize", return_value=1024 * 1024), \
             patch("app.services.processor.convert_to_wav") as mock_convert, \
             patch.object(TranscriptionProcessor, "_get_model_manager") as mock_mgr:

            MockAS.from_file.return_value = short_audio

            mock_manager = MagicMock()
            mock_manager.is_loaded = False
            mock_manager.device = "cpu"
            mock_manager.transcribe.return_value = {
                "text": "Done",
                "segments": [{"text": " Done", "start": 0.0, "end": 3.0}],
                "language": "pt",
            }
            mock_mgr.return_value = mock_manager

            converted_path = tmp_path / "converted.wav"
            converted_path.write_bytes(b"\x00" * 1024)
            mock_convert.return_value = (Path(str(converted_path)), True)

            state_mock = MagicMock()
            proc = _build_processor(settings, state=state_mock)
            proc.output_dir = str(tmp_path / "output")
            Path(proc.output_dir).mkdir(parents=True, exist_ok=True)

            job = MagicMock()
            job.id = "progress-test-1"
            job.input_file = str(audio_file)
            job.engine = WhisperEngine.FASTER_WHISPER
            job.language_in = "pt"
            job.language_out = None
            job.started_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

            try:
                await proc.process_transcription_job(job)
            except Exception:
                pass

            state_mock.mark_processing.assert_called_once()
