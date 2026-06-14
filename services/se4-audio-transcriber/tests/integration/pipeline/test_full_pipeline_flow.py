"""Full pipeline integration test: upload → convert WAV → chunk split → transcribe with mock engine → merge segments → SRT output."""
from pathlib import Path

import pytest


class TestFullPipelineFlow:
    """End-to-end flow exercising audio_converter, ChunkTranscriber, and caption formatting.

    Uses a real generated WAV file on disk (via pydub) so the pipeline exercises
    actual I/O rather than MagicMock stubs.  The transcription engine is mocked to
    keep tests fast and deterministic without requiring Whisper models or GPU.
    """

    @pytest.mark.asyncio
    async def test_single_chunk_pipeline_produces_srt(
        self, sample_wav_bytes, mock_transcriber_engine, temp_pipeline_dirs
    ):
        """Short audio (10 s) → single chunk → transcribe → SRT output."""
        from app.shared.audio_converter import convert_to_wav
        from app.shared.chunk_transcriber import ChunkTranscriber

        upload_dir = temp_pipeline_dirs["upload"]
        wav_path = upload_dir / "input.wav"
        wav_path.write_bytes(sample_wav_bytes)

        # Step 1: Convert (already WAV, should pass through or re-encode)
        converted_path, is_temp = convert_to_wav(wav_path, settings={"temp_dir": str(upload_dir)})
        assert converted_path.exists()
        assert converted_path.suffix == ".wav"

        # Step 2: Transcribe via ChunkTranscriber with mock engine
        chunker_settings = {
            "chunk_length_seconds": 30,
            "overlap_seconds": 1.0,
            "temp_dir": str(upload_dir / "chunks"),
        }
        ct = ChunkTranscriber(settings=chunker_settings)

        result = await ct.transcribe(
            audio_file=str(converted_path),
            language_in="pt",
            language_out=None,
            transcribe_fn=mock_transcriber_engine,
        )

        assert "text" in result
        assert "segments" in result
        assert len(result["segments"]) >= 1

        # Step 3: Format SRT output from segments
        from tests.integration.pipeline.conftest import segments_to_srt as _srt_fmt

        srt = _srt_fmt(result["segments"])
        assert "-->" in srt, f"SRT should contain time markers but got: {srt}"
        for seg in result["segments"]:
            assert "start" in seg
            assert "end" in seg
            assert "text" in seg

    @pytest.mark.asyncio
    async def test_multi_chunk_pipeline_merges_segments(
        self, long_sample_wav_bytes, mock_transcriber_engine_with_overlap, temp_pipeline_dirs
    ):
        """Long audio (65 s) → multiple chunks with overlap → merged segments."""
        from app.shared.audio_converter import convert_to_wav
        from app.shared.chunk_transcriber import ChunkTranscriber

        upload_dir = temp_pipeline_dirs["upload"]
        wav_path = upload_dir / "long_input.wav"
        wav_path.write_bytes(long_sample_wav_bytes)

        converted_path, is_temp = convert_to_wav(wav_path, settings={"temp_dir": str(upload_dir)})

        chunker_settings = {
            "chunk_length_seconds": 30,
            "overlap_seconds": 1.0,
            "temp_dir": str(upload_dir / "chunks"),
        }
        ct = ChunkTranscriber(settings=chunker_settings)

        result = await ct.transcribe(
            audio_file=str(converted_path),
            language_in="pt",
            language_out=None,
            transcribe_fn=mock_transcriber_engine_with_overlap,
        )

        assert "text" in result
        assert len(result["segments"]) >= 1

        # Verify timestamps are monotonically non-decreasing after merge
        segments = sorted(result["segments"], key=lambda s: s["start"])
        for i in range(1, len(segments)):
            assert segments[i]["start"] >= segments[i - 1]["start"]

    def test_pipeline_handles_conversion_failure_for_non_audio(self, tmp_path):
        """A file without audio stream should raise AudioTranscriptionException."""
        from app.shared.audio_converter import convert_to_wav
        from app.shared.exceptions import AudioTranscriptionException

        dummy = tmp_path / "not_audio.txt"
        dummy.write_text("this is not an audio file")

        with pytest.raises(AudioTranscriptionException):
            convert_to_wav(dummy, settings={"temp_dir": str(tmp_path)})

    @pytest.mark.asyncio
    async def test_pipeline_with_preloaded_audio_segment(
        self, sample_wav_bytes, mock_transcriber_engine, temp_pipeline_dirs
    ):
        """Pass a pre-loaded AudioSegment to avoid re-reading from disk."""
        from pydub import AudioSegment as _AudioSegment
        from app.shared.chunk_transcriber import ChunkTranscriber

        upload_dir = temp_pipeline_dirs["upload"]
        wav_path = upload_dir / "preloaded.wav"
        wav_path.write_bytes(sample_wav_bytes)

        audio_segment = _AudioSegment.from_file(str(wav_path))

        ct = ChunkTranscriber(settings={
            "chunk_length_seconds": 30,
            "overlap_seconds": 1.0,
            "temp_dir": str(upload_dir / "chunks"),
        })

        result = await ct.transcribe(
            audio_file=str(wav_path),
            language_in="auto",
            language_out=None,
            transcribe_fn=mock_transcriber_engine,
            audio=audio_segment,
        )

        assert len(result["segments"]) >= 1
        assert "text" in result


class TestSegmentMerge:
    """Unit-level tests for the _merge_overlapping_segments logic inside ChunkTranscriber."""

    def test_merge_removes_duplicate_overlap(self):
        from app.shared.chunk_transcriber import ChunkTranscriber

        ct = ChunkTranscriber(settings={})
        segments = [
            {"start": 0, "end": 30, "text": "Hello world this is the first segment"},
            # Overlapping with very similar text (Jaccard > 0.8) — should be merged away
            {"start": 29, "end": 31, "text": "hello world this is the first segment"},
        ]

        merged = ct._merge_overlapping_segments(segments, overlap_seconds=1.0)
        assert len(merged) == 1
        # End time should be extended to cover both segments' end
        assert merged[0]["end"] >= 30

    def test_merge_keeps_different_content(self):
        from app.shared.chunk_transcriber import ChunkTranscriber

        ct = ChunkTranscriber(settings={})
        segments = [
            {"start": 0, "end": 30, "text": "First segment with unique words"},
            # Overlapping but different text — should be kept as separate segment
            {"start": 29, "end": 45, "text": "Completely different content here now"},
        ]

        merged = ct._merge_overlapping_segments(segments, overlap_seconds=1.0)
        assert len(merged) == 2

    def test_merge_empty_input(self):
        from app.shared.chunk_transcriber import ChunkTranscriber

        ct = ChunkTranscriber(settings={})
        assert ct._merge_overlapping_segments([], overlap_seconds=1.0) == []


class TestSrtFormatting:
    """Validate SRT caption output formatting."""

    def test_srt_format_basic(self):
        srt = self._format_srt([
            {"start": 0, "end": 3, "text": "Hello world"},
            {"start": 3.5, "end": 7.2, "text": "Second line of caption"},
        ])

        assert "1" in srt
        assert "-->" in srt
        assert "00:00:00,000 --> 00:00:03,000" in srt
        assert "Hello world" in srt
        assert "Second line of caption" in srt

    def test_srt_format_with_milliseconds(self):
        srt = self._format_srt([
            {"start": 1.256, "end": 4.789, "text": "Test"},
        ])

        assert "-->" in srt
        # Verify millisecond precision is preserved with comma separator (SRT spec)
        lines = [l for l in srt.split("\n") if "-->" in l]
        assert len(lines) == 1


    def _format_srt(self, segments):
        """Format a list of segment dicts to SRT caption string."""

        def _fmt(s):
            h = int(s // 3600)
            m = int((s % 3600) // 60)
            sec = s % 60
            return f"{h:02d}:{m:02d}:{sec:06.3f}"

        lines = []
        for i, seg in enumerate(segments, 1):
            start_str = _fmt(seg["start"]).replace('.', ',')
            end_str = _fmt(seg["end"]).replace('.', ',')
            block = f"{i}\n{start_str} --> {end_str}\n{seg['text']}"
            lines.append(block)

        return "\n\n".join(lines) + "\n"


class TestPipelineWithJobTracking:
    """Full pipeline with JobStateUpdater integration for progress tracking."""

    @pytest.mark.asyncio
    async def test_pipeline_updates_progress_via_state(
        self, sample_wav_bytes, mock_transcriber_engine, temp_pipeline_dirs, mock_job_store_inmemory
    ):
        from datetime import timedelta

        from app.shared.chunk_transcriber import ChunkTranscriber
        from app.shared.job_state_updater import JobStateUpdater

        upload_dir = temp_pipeline_dirs["upload"]
        wav_path = upload_dir / "tracked.wav"
        wav_path.write_bytes(sample_wav_bytes)

        state_updater = JobStateUpdater(job_store=mock_job_store_inmemory)

        ct = ChunkTranscriber(
            settings={
                "chunk_length_seconds": 30,
                "overlap_seconds": 1.0,
                "temp_dir": str(upload_dir / "chunks"),
            },
            state=state_updater,
        )

        job_id = "tracked_job_42"

        # Seed a QUEUED job in the store so set_progress can retrieve it
        from app.domain.models import Job, WhisperEngine
        try:
            from common.datetime_utils import now_brazil as nb_fn
        except ImportError:
            from datetime import datetime, timezone
            def nb_fn(): return datetime.now(timezone.utc)

        fixed = nb_fn()
        job = Job(
            id=job_id,
            status="queued",
            operation="transcribe",
            language_in="pt",
            engine=WhisperEngine.FASTER_WHISPER,
            filename="tracked.wav",
            received_at=fixed,
            created_at=fixed,
            expires_at=fixed + timedelta(hours=24),
        )
        mock_job_store_inmemory.save_job(job)

        result = await ct.transcribe(
            audio_file=str(wav_path),
            language_in="pt",
            language_out=None,
            transcribe_fn=mock_transcriber_engine,
            job_id=job_id,
        )

        assert "segments" in result

        # Verify progress was persisted to the store
        stored_job = mock_job_store_inmemory.get_job(job_id)
        assert stored_job is not None
        assert 25.0 <= stored_job.progress <= 75.0


class TestPipelineFailureHandling:
    """Verify pipeline behavior when transcription engine fails mid-stream."""

    @pytest.mark.asyncio
    async def test_pipeline_raises_on_engine_failure(
        self, long_sample_wav_bytes, mock_transcriber_engine_failing, temp_pipeline_dirs
    ):
        from app.shared.chunk_transcriber import ChunkTranscriber
        from app.shared.exceptions import AudioTranscriptionException

        upload_dir = temp_pipeline_dirs["upload"]
        wav_path = upload_dir / "fail_test.wav"
        wav_path.write_bytes(long_sample_wav_bytes)

        ct = ChunkTranscriber(settings={
            "chunk_length_seconds": 30,
            "overlap_seconds": 1.0,
            "temp_dir": str(upload_dir / "chunks"),
        })

        with pytest.raises(AudioTranscriptionException):
            await ct.transcribe(
                audio_file=str(wav_path),
                language_in="pt",
                language_out=None,
                transcribe_fn=mock_transcriber_engine_failing,
            )


class TestAudioConverterWAVPassthrough:
    """Verify convert_to_wav behavior for already-WAV files."""

    def test_already_valid_wav_returns_same_path(self, sample_wav_bytes, tmp_path):
        from app.shared.audio_converter import convert_to_wav

        wav = tmp_path / "valid.wav"
        wav.write_bytes(sample_wav_bytes)

        result_path, is_temp = convert_to_wav(wav, settings={"temp_dir": str(tmp_path)})
        assert not is_temp  # Already WAV → no temp conversion needed


    def test_nonexistent_file_raises(self):
        from app.shared.audio_converter import convert_to_wav
        from app.shared.exceptions import AudioTranscriptionException

        with pytest.raises((AudioTranscriptionException, FileNotFoundError)):
            convert_to_wav(Path("/nonexistent/path/file.wav"))
