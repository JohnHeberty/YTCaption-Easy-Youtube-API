"""Unit tests for AudioChunker (split, export_chunk, cleanup_chunk)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydub import AudioSegment as RealAudioSegment

from app.shared.audio_chunker import AudioChunk, AudioChunker


def _make_mock_segment(duration_ms: int):
    """Create a mock AudioSegment whose __len__ returns *duration_ms*."""
    seg = MagicMock()
    type(seg).__len__ = lambda self=seg: duration_ms  # noqa: B026
    return seg


def _make_real_silent_segment(seconds: float) -> RealAudioSegment:
    """Create a real silent pydub AudioSegment (needed for export I/O tests)."""
    sample_width = 1
    frame_rate = 8000
    channels = 1
    return RealAudioSegment.silent(
        duration=int(seconds * 1000),
        frame_rate=frame_rate,
    )


# ---------------------------------------------------------------------------
# split – correct number of chunks & boundaries
# ---------------------------------------------------------------------------


class TestSplitExactFit:

    def test_single_chunk_when_audio_fits(self):
        """Audio shorter than chunk_length produces exactly one chunk."""
        audio = _make_mock_segment(15_000)  # 15 s < 30 s default
        chunker = AudioChunker(chunk_length_seconds=30, overlap_seconds=1.0)

        chunks = chunker.split(audio)

        assert len(chunks) == 1
        assert isinstance(chunks[0], AudioChunk)
        assert chunks[0].number == 0
        assert chunks[0].start_time_s == 0.0

    def test_two_chunks_when_audio_exceeds_one_step(self):
        """65 s audio with 30 s chunk and 1 s overlap -> step=29 s -> ceil(65/29)=3."""
        audio = _make_mock_segment(65_000)
        chunker = AudioChunker(chunk_length_seconds=30, overlap_seconds=1.0)

        chunks = chunker.split(audio)

        # positions: 0, 29s -> end at 58; still < 65 so third starts at 58
        assert len(chunks) == 3
        assert chunks[0].start_time_s == pytest.approx(0.0)
        assert chunks[1].start_time_s == pytest.approx(29.0)
        assert chunks[2].start_time_s == pytest.approx(58.0)

    def test_three_chunks_90s_audio(self):
        """90 s audio, 30 s chunk, 0 overlap -> exactly 3 non-overlapping chunks."""
        audio = _make_mock_segment(90_000)
        chunker = AudioChunker(chunk_length_seconds=30, overlap_seconds=0.0)

        chunks = chunker.split(audio)

        assert len(chunks) == 3
        for i, c in enumerate(chunks):
            assert c.number == i
            assert c.start_time_s == pytest.approx(i * 30.0)


class TestSplitOverlap:

    def test_overlap_advances_by_chunk_minus_overlap(self):
        """step = chunk_length - overlap."""
        audio = _make_mock_segment(10_000)
        chunker = AudioChunker(chunk_length_seconds=5, overlap_seconds=2.0)

        chunks = chunker.split(audio)

        # step_ms = 3000 -> positions: 0, 3s, 6s, 9s (4th at 12 >= 10 stops before loop body? no: while < duration so pos=9 enters, then next is 12 which exits)
        assert len(chunks) == 4
        expected_starts = [0.0, 3.0, 6.0, 9.0]
        for chunk, exp in zip(chunks, expected_starts):
            assert chunk.start_time_s == pytest.approx(exp)

    def test_large_overlap_fewer_chunks(self):
        """Large overlap means fewer steps to cover the same duration."""
        audio = _make_mock_segment(60_000)  # 60 s
        chunker = AudioChunker(chunk_length_seconds=30, overlap_seconds=15.0)

        chunks = chunker.split(audio)

        step_ms = 15_000  # 30-15
        expected_count = -(-60 // 15)  # ceil division -> 4
        assert len(chunks) == expected_count


class TestSplitSmallAudio:

    def test_audio_smaller_than_chunk_returns_single(self):
        """Any audio shorter than one step (chunk_length - overlap) returns exactly one chunk."""
        # With chunk=30s, overlap=1s -> step = 29_000 ms.
        # Durations < 29_000 produce a single chunk because the while loop exits after pos += step >= duration.
        for duration_ms in [1_000, 5_000, 28_999]:
            audio = _make_mock_segment(duration_ms)
            chunker = AudioChunker(chunk_length_seconds=30, overlap_seconds=1.0)

            chunks = chunker.split(audio)

            assert len(chunks) == 1, f"Expected 1 chunk for {duration_ms} ms"
            assert chunks[0].number == 0
            assert chunks[0].start_time_s == 0.0

    def test_audio_just_over_step_produces_two_chunks(self):
        """When duration exceeds one step the loop produces a second (shorter) chunk."""
        # With chunk=30s, overlap=1s -> step = 29_000 ms.
        audio = _make_mock_segment(29_500)
        chunker = AudioChunker(chunk_length_seconds=30, overlap_seconds=1.0)

        chunks = chunker.split(audio)

        assert len(chunks) == 2
        assert chunks[0].start_time_s == pytest.approx(0.0)
        assert chunks[1].start_time_s == pytest.approx(29.0)


class TestSplitEdgeCases:

    def test_overlap_equals_chunk_raises(self):
        """overlap_seconds >= chunk_length_seconds must raise ValueError."""
        audio = _make_mock_segment(60_000)
        chunker = AudioChunker(chunk_length_seconds=5, overlap_seconds=5.0)

        with pytest.raises(ValueError, match="must be greater than"):
            chunker.split(audio)

    def test_overlap_greater_than_chunk_raises(self):
        audio = _make_mock_segment(60_000)
        chunker = AudioChunker(chunk_length_seconds=3, overlap_seconds=5.0)

        with pytest.raises(ValueError, match="must be greater than"):
            chunker.split(audio)


# ---------------------------------------------------------------------------
# export_chunk – creates temp WAV file on disk
# ---------------------------------------------------------------------------


class TestExportChunk:

    def test_creates_file_in_temp_dir(self, tmp_path):
        """export_chunk writes a .wav file into the configured temp dir."""
        audio = _make_real_silent_segment(30.0)
        chunker = AudioChunker(temp_dir=str(tmp_path / "chunks"))

        chunks = chunker.split(audio)
        path = chunker.export_chunk(0, chunks[0])

        assert path.exists()
        assert path.suffix == ".wav"
        assert path.name == "chunk_0.wav"
        assert (tmp_path / "chunks") in path.parents or str(tmp_path / "chunks") == str(path.parent)

    def test_creates_temp_dir_if_missing(self, tmp_path):
        """The temp directory is created automatically if it does not exist."""
        audio = _make_real_silent_segment(30.0)
        nested = tmp_path / "a" / "b" / "c"
        chunker = AudioChunker(temp_dir=str(nested))

        chunks = chunker.split(audio)
        path = chunker.export_chunk(5, chunks[0])

        assert nested.exists()
        assert path.name == "chunk_5.wav"


# ---------------------------------------------------------------------------
# cleanup_chunk – removes temp file from filesystem
# ---------------------------------------------------------------------------


class TestCleanupChunk:

    def test_removes_existing_file(self, tmp_path):
        """cleanup_chunk deletes the file if it exists."""
        dummy = tmp_path / "remove_me.wav"
        dummy.touch()

        chunker = AudioChunker(temp_dir=str(tmp_path))
        chunker.cleanup_chunk(dummy)

        assert not dummy.exists()

    def test_no_error_when_file_missing(self, tmp_path):
        """cleanup_chunk is a no-op when the file does not exist."""
        missing = tmp_path / "does_not_exist.wav"
        chunker = AudioChunker(temp_dir=str(tmp_path))

        # Should NOT raise
        chunker.cleanup_chunk(missing)


# ---------------------------------------------------------------------------
# should_chunk – static helper threshold logic
# ---------------------------------------------------------------------------


class TestShouldChunk:

    def test_below_default_threshold(self):
        assert not AudioChunker.should_chunk(299.0)

    def test_at_exact_boundary(self):
        # 300 is NOT greater than 300 -> False (strict >)
        assert not AudioChunker.should_chunk(300.0)

    def test_above_default_threshold(self):
        assert AudioChunker.should_chunk(301.0)

    def test_custom_lower_threshold(self):
        assert AudioChunker.should_chunk(59, min_duration_for_chunks=60) is False
        assert AudioChunker.should_chunk(61, min_duration_for_chunks=60) is True


# ---------------------------------------------------------------------------
# Integration: split -> export -> cleanup round-trip on real filesystem
# ---------------------------------------------------------------------------


class TestRoundTripExportCleanup:

  def test_full_lifecycle(self, tmp_path):
        """Split audio, export chunks to disk, then clean up all files."""
        duration_s = 75.0
        chunk_length_s = 30.0
        overlap_s = 2.0

        audio = _make_real_silent_segment(duration_s)
        temp_dir = tmp_path / "roundtrip"
        chunker = AudioChunker(
            temp_dir=str(temp_dir),
            chunk_length_seconds=chunk_length_s,
            overlap_seconds=overlap_s,
        )

        chunks = chunker.split(audio)
        assert len(chunks) > 1

        exported_paths: list[Path] = []
        for i, chunk in enumerate(chunks):
            p = chunker.export_chunk(i, chunk)
            assert p.exists()
            exported_paths.append(p)

        # Clean up all files.
        for p in exported_paths:
            chunker.cleanup_chunk(p)

        for p in exported_paths:
            assert not p.exists(), f"File {p} should have been removed."


# ---------------------------------------------------------------------------
# Chunk metadata correctness (numbering, start_time ordering)
# ---------------------------------------------------------------------------


class TestChunkMetadata:

    def test_numbers_are_sequential(self):
        audio = _make_mock_segment(120_000)  # 120 s
        chunker = AudioChunker(chunk_length_seconds=30, overlap_seconds=5.0)

        chunks = chunker.split(audio)

        for i, c in enumerate(chunks):
            assert c.number == i

    def test_start_times_are_ascending(self):
        audio = _make_mock_segment(120_000)
        chunker = AudioChunker(chunk_length_seconds=30, overlap_seconds=5.0)

        chunks = chunker.split(audio)

        for j in range(1, len(chunks)):
            assert chunks[j].start_time_s > chunks[j - 1].start_time_s
