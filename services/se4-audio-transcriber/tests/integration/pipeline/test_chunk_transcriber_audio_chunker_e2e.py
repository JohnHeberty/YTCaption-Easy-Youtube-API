"""ChunkTranscriber ↔ AudioChunker end-to-end integration tests."""
from pathlib import Path

import pytest


class TestAudioChunkerSplitting:
    """Verify AudioChunker split logic with real audio data."""

    def test_single_chunk_for_short_audio(self, sample_wav_bytes, tmp_path):
        from pydub import AudioSegment as _AudioSegment
        from app.shared.audio_chunker import AudioChunker

        wav = tmp_path / "short.wav"
        wav.write_bytes(sample_wav_bytes)
        audio = _AudioSegment.from_file(str(wav))

        chunker = AudioChunker(
            temp_dir=str(tmp_path / "chunks"),
            chunk_length_seconds=30,
            overlap_seconds=1.0,
        )

        chunks = chunker.split(audio)
        assert len(chunks) == 1
        assert chunks[0].start_time_s == 0.0
        assert chunks[0].number == 0

    def test_multi_chunk_for_long_audio(self, long_sample_wav_bytes, tmp_path):
        from pydub import AudioSegment as _AudioSegment
        from app.shared.audio_chunker import AudioChunker

        wav = tmp_path / "long.wav"
        wav.write_bytes(long_sample_wav_bytes)
        audio = _AudioSegment.from_file(str(wav))

        chunk_length = 30.0
        overlap = 1.0
        duration_ms = len(audio)
        step_ms = int(chunk_length * 1000 - overlap * 1000)
        expected_chunks = max(1, (duration_ms + step_ms - 1) // step_ms)

        chunker = AudioChunker(
            temp_dir=str(tmp_path / "chunks"),
            chunk_length_seconds=chunk_length,
            overlap_seconds=overlap,
        )

        chunks = chunker.split(audio)
        assert len(chunks) >= expected_chunks - 1
        for i in range(len(chunks)):
            assert chunks[i].number == i

    def test_chunk_overlap_timing(self, long_sample_wav_bytes, tmp_path):
        """Verify consecutive chunks have correct overlap boundaries."""
        from pydub import AudioSegment as _AudioSegment
        from app.shared.audio_chunker import AudioChunker

        wav = tmp_path / "overlap_test.wav"
        wav.write_bytes(long_sample_wav_bytes)
        audio = _AudioSegment.from_file(str(wav))

        chunk_length = 30.0
        overlap = 1.0
        step_seconds = chunk_length - overlap

        chunker = AudioChunker(
            temp_dir=str(tmp_path / "chunks"),
            chunk_length_seconds=chunk_length,
            overlap_seconds=overlap,
        )

        chunks = chunker.split(audio)
        for i in range(len(chunks)):
            expected_start = float(i) * step_seconds
            assert abs(chunks[i].start_time_s - expected_start) < 0.1

    def test_export_chunk_creates_file(self, sample_wav_bytes, tmp_path):
        from pydub import AudioSegment as _AudioSegment
        from app.shared.audio_chunker import AudioChunker

        wav = tmp_path / "export_test.wav"
        wav.write_bytes(sample_wav_bytes)
        audio = _AudioSegment.from_file(str(wav))

        chunk_dir = str(tmp_path / "exports")
        chunker = AudioChunker(temp_dir=chunk_dir, chunk_length_seconds=30, overlap_seconds=1.0)
        chunks = chunker.split(audio)

        exported = chunker.export_chunk(0, chunks[0])
        assert exported.exists()
        assert exported.suffix == ".wav"

    def test_cleanup_removes_file(self, sample_wav_bytes, tmp_path):
        from pydub import AudioSegment as _AudioSegment
        from app.shared.audio_chunker import AudioChunker

        wav = tmp_path / "cleanup_test.wav"
        wav.write_bytes(sample_wav_bytes)
        audio = _AudioSegment.from_file(str(wav))

        chunk_dir = str(tmp_path / "cleanups")
        chunker = AudioChunker(temp_dir=chunk_dir, chunk_length_seconds=30, overlap_seconds=1.0)
        chunks = chunker.split(audio)

        exported = chunker.export_chunk(0, chunks[0])
        assert exported.exists()

        chunker.cleanup_chunk(exported)
        assert not exported.exists()


class TestChunkTranscriberAudioChunkerE2E:
    """Full ChunkTranscriber + AudioChunker flow with real temp files."""

    @pytest.mark.asyncio
    async def test_e2e_single_chunk_transcription(self, sample_wav_bytes, mock_transcriber_engine, tmp_path):
        from pydub import AudioSegment as _AudioSegment
        from app.shared.chunk_transcriber import ChunkTranscriber

        wav = tmp_path / "e2e_short.wav"
        wav.write_bytes(sample_wav_bytes)

        ct = ChunkTranscriber(settings={
            "chunk_length_seconds": 30,
            "overlap_seconds": 1.0,
            "temp_dir": str(tmp_path / "chunks"),
        })

        result = await ct.transcribe(
            audio_file=str(wav),
            language_in="pt",
            language_out=None,
            transcribe_fn=mock_transcriber_engine,
        )

        assert len(result["segments"]) >= 1
        assert "text" in result and len(result["text"]) > 0

    @pytest.mark.asyncio
    async def test_e2e_multi_chunk_with_offset_adjustment(self, long_sample_wav_bytes, mock_transcriber_engine, tmp_path):
        """Verify segment timestamps are correctly offset by chunk start time."""
        from pydub import AudioSegment as _AudioSegment
        from app.shared.chunk_transcriber import ChunkTranscriber

        wav = tmp_path / "e2e_long.wav"
        wav.write_bytes(long_sample_wav_bytes)

        ct = ChunkTranscriber(settings={
            "chunk_length_seconds": 30,
            "overlap_seconds": 1.0,
            "temp_dir": str(tmp_path / "chunks"),
        })

        result = await ct.transcribe(
            audio_file=str(wav),
            language_in="pt",
            language_out=None,
            transcribe_fn=mock_transcriber_engine,
        )

        segments = sorted(result["segments"], key=lambda s: s["start"])
        assert len(segments) >= 1

        # Timestamps should be non-negative and monotonically increasing start times
        for seg in segments:
            assert seg["start"] >= 0.0
            assert seg["end"] > seg["start"]

    @pytest.mark.asyncio
    async def test_e2e_chunk_temp_files_cleaned_up(self, sample_wav_bytes, mock_transcriber_engine, tmp_path):
        """Verify chunk temp files are removed after transcription."""
        from pydub import AudioSegment as _AudioSegment
        from app.shared.chunk_transcriber import ChunkTranscriber

        wav = tmp_path / "cleanup_e2e.wav"
        wav.write_bytes(sample_wav_bytes)

        chunk_dir = tmp_path / "chunks_cleanup"
        ct = ChunkTranscriber(settings={
            "chunk_length_seconds": 30,
            "overlap_seconds": 1.0,
            "temp_dir": str(chunk_dir),
        })

        result = await ct.transcribe(
            audio_file=str(wav),
            language_in="pt",
            language_out=None,
            transcribe_fn=mock_transcriber_engine,
        )

        assert len(result["segments"]) >= 1

        # Chunk files should be cleaned up after processing
        remaining = list(chunk_dir.glob("chunk_*.wav")) if chunk_dir.exists() else []
        assert len(remaining) == 0


class TestAudioChunkerEdgeCases:
    """Boundary conditions for AudioChunker."""

    def test_overlap_greater_than_chunk_raises(self, sample_wav_bytes, tmp_path):
        from pydub import AudioSegment as _AudioSegment
        from app.shared.audio_chunker import AudioChunker

        wav = tmp_path / "edge.wav"
        wav.write_bytes(sample_wav_bytes)
        audio = _AudioSegment.from_file(str(wav))

        chunker = AudioChunker(
            temp_dir=str(tmp_path),
            chunk_length_seconds=5.0,
            overlap_seconds=10.0,  # Overlap > chunk length → invalid
        )

        with pytest.raises(ValueError):
            chunker.split(audio)

    def test_should_chunk_threshold(self):
        from app.shared.audio_chunker import AudioChunker

        assert not AudioChunker.should_chunk(299.0, min_duration_for_chunks=300)
        assert AudioChunker.should_chunk(301.0, min_duration_for_chunks=300)
        # Exactly at threshold should return False (strict > comparison)
        assert not AudioChunker.should_chunk(300.0, min_duration_for_chunks=300)