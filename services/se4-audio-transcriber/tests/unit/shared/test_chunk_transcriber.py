"""Testes unitários para ChunkTranscriber."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.shared.chunk_transcriber import ChunkTranscriber


# ---------------------------------------------------------------------------
# _text_similarity
# ---------------------------------------------------------------------------


class TestTextSimilarity:

    def test_identical_texts_return_one(self):
        assert ChunkTranscriber._text_similarity("hello world", "hello world") == 1.0

    def test_completely_different_texts_near_zero(self):
        result = ChunkTranscriber._text_similarity(
            "alpha beta gamma", "delta epsilon zeta"
        )
        assert result < 0.01

    def test_empty_strings_return_zero(self):
        assert ChunkTranscriber._text_similarity("", "") == 0.0
        assert ChunkTranscriber._text_similarity("hello", "") == 0.0
        assert ChunkTranscriber._text_similarity("", "world") == 0.0

    def test_single_word_overlap_intermediate(self):
        result = ChunkTranscriber._text_similarity(
            "the cat sat on the mat", "the dog ran across"
        )
        # shared word: "the"; union has more words -> intermediate value
        assert 0.0 < result < 1.0


# ---------------------------------------------------------------------------
# _merge_overlapping_segments
# ---------------------------------------------------------------------------


class TestMergeOverlappingSegments:

    def test_no_overlap_kept_intact(self):
        transcriber = ChunkTranscriber(settings={})
        segments = [
            {"start": 0, "end": 5, "text": "primeiro segmento"},
            {"start": 10, "end": 15, "text": "segundo segmento"},
        ]
        result = transcriber._merge_overlapping_segments(segments, overlap_seconds=1.0)
        assert len(result) == 2

    def test_overlap_duplicate_text_merges_extending_end(self):
        transcriber = ChunkTranscriber(settings={})
        segments = [
            {"start": 0, "end": 5, "text": "mesmo texto duplicado"},
            {"start": 4.5, "end": 9, "text": "mesmo texto duplicado"},
        ]
        result = transcriber._merge_overlapping_segments(segments, overlap_seconds=1.0)
        assert len(result) == 1
        assert result[0]["start"] == 0
        # end should be extended to the later segment's end (9 > 5)
        assert result[0]["end"] == 9

    def test_overlap_different_content_both_kept(self):
        transcriber = ChunkTranscriber(settings={})
        segments = [
            {"start": 0, "end": 5, "text": "conteúdo totalmente diferente um"},
            {"start": 4.5, "end": 9, "text": "outro conteúdo completamente distinto dois"},
        ]
        result = transcriber._merge_overlapping_segments(segments, overlap_seconds=1.0)
        assert len(result) == 2

    def test_empty_list_returns_empty(self):
        transcriber = ChunkTranscriber(settings={})
        result = transcriber._merge_overlapping_segments([], overlap_seconds=1.0)
        assert result == []


# ---------------------------------------------------------------------------
# Edge cases for _merge with similarity threshold 0.8
# ---------------------------------------------------------------------------


class TestMergeSimilarityThreshold:

    def test_similarity_below_threshold_keeps_both(self):
        transcriber = ChunkTranscriber(settings={})
        segments = [
            {"start": 0, "end": 10, "text": "hello world foo"},
            {"start": 9, "end": 15, "text": "hello world bar"},
        ]
        # Similarity is 2/4=0.5 < 0.8 -> both kept
        result = transcriber._merge_overlapping_segments(segments, overlap_seconds=1.0)
        assert len(result) == 2

    def test_completely_different_text_keeps_both(self):
        transcriber = ChunkTranscriber(settings={})
        segments = [
            {"start": 0, "end": 10, "text": "aaaa bbbb cccc dddd"},
            {"start": 9, "end": 15, "text": "eeee ffff gggg hhhh"},
        ]
        result = transcriber._merge_overlapping_segments(segments, overlap_seconds=1.0)
        assert len(result) == 2

    def test_identical_text_high_similarity_merges(self):
        transcriber = ChunkTranscriber(settings={})
        segments = [
            {"start": 0, "end": 5, "text": "hello world"},
            {"start": 4, "end": 9, "text": "hello world"},
        ]
        result = transcriber._merge_overlapping_segments(segments, overlap_seconds=1.0)
        assert len(result) == 1

    def test_merge_does_not_extend_when_end_is_earlier(self):
        transcriber = ChunkTranscriber(settings={})
        segments = [
            {"start": 0, "end": 12, "text": "same text here"},
            {"start": 8, "end": 9, "text": "same text here"},
        ]
        result = transcriber._merge_overlapping_segments(segments, overlap_seconds=1.0)
        assert len(result) == 1
        # end should remain at the larger value (12), not shrink to 9
        assert result[0]["end"] == 12


# ---------------------------------------------------------------------------
# transcribe (async) – full flow with mocks
# ---------------------------------------------------------------------------


class TestAsyncTranscribe:

    def _make_mock_segment(self):
        seg = MagicMock()
        type(seg).__len__ = lambda self: 60_000
        return seg

    @pytest.mark.asyncio
    async def test_full_flow_adjusts_timestamps(self):
        """Timestamps in segments should be shifted by the chunk offset."""
        from app.shared.audio_chunker import AudioChunk as RealAudioChunk

        settings = {
            "chunk_length_seconds": 30,
            "overlap_seconds": 1.0,
            "temp_dir": "/tmp/test_chunks",
        }

        mock_audio_segment = self._make_mock_segment()

        audio_chunk = MagicMock(spec=RealAudioChunk)
        audio_chunk.start_time_s = 30.0

        transcribe_fn = MagicMock(return_value={
            "text": "texto transcrito do chunk",
            "segments": [
                {"start": 0, "end": 5, "text": "palavra um"},
                {"start": 6, "end": 12, "text": "palavra dois"},
            ],
        })

        mock_chunker = MagicMock()
        mock_chunker.export_chunk.return_value = Path("/tmp/chunk_0.wav")

        transcriber = ChunkTranscriber(settings=settings)

        with patch("pathlib.Path.exists", return_value=True):
            with patch(
                "app.shared.chunk_transcriber.AudioChunker", return_value=mock_chunker
            ):
                mock_chunker.split.return_value = [audio_chunk]

                result = await transcriber.transcribe(
                    audio_file="/tmp/test.mp3",
                    language_in="pt",
                    language_out=None,
                    transcribe_fn=transcribe_fn,
                    job_id=None,
                    audio=mock_audio_segment,
                )

        assert result["text"] == "texto transcrito do chunk"

        segments = result["segments"]
        assert len(segments) == 2
        assert segments[0]["start"] == pytest.approx(30.0 + 0)
        assert segments[0]["end"] == pytest.approx(30.0 + 5)
        assert segments[1]["start"] == pytest.approx(30.0 + 6)
        assert segments[1]["end"] == pytest.approx(30.0 + 12)

    @pytest.mark.asyncio
    async def test_progress_tracking_via_state_updater(self):
        """Progress should be set on the state updater for each chunk."""
        from app.shared.audio_chunker import AudioChunk as RealAudioChunk

        settings = {
            "chunk_length_seconds": 30,
            "overlap_seconds": 1.0,
            "temp_dir": "/tmp/test_chunks",
        }

        mock_audio_segment = self._make_mock_segment()

        audio_mock1 = MagicMock(spec=RealAudioChunk)
        audio_mock1.start_time_s = 0.0

        audio_mock2 = MagicMock(spec=RealAudioChunk)
        audio_mock2.start_time_s = 30.0

        mock_chunker = MagicMock()
        paths = [Path("/tmp/chunk_0.wav"), Path("/tmp/chunk_1.wav")]
        mock_chunker.export_chunk.side_effect = lambda i, _: paths[i]

        transcribe_fn = MagicMock(return_value={
            "text": "chunk text",
            "segments": [{"start": 0, "end": 3, "text": "seg"}],
        })

        state_updater = MagicMock()
        transcriber = ChunkTranscriber(settings=settings, state=state_updater)

        with patch("pathlib.Path.exists", return_value=True):
            with patch(
                "app.shared.chunk_transcriber.AudioChunker", return_value=mock_chunker
            ):
                mock_chunker.split.return_value = [audio_mock1, audio_mock2]

                await transcriber.transcribe(
                    audio_file="/tmp/test.mp3",
                    language_in="pt",
                    language_out=None,
                    transcribe_fn=transcribe_fn,
                    job_id="job-42",
                    audio=mock_audio_segment,
                )

        # 2 chunks -> progress called twice:
        #   i=0 -> 25 + 50*(1/2) = 50.0
        #   i=1 -> 25 + 50*(2/2) = 75.0
        calls = state_updater.set_progress.call_args_list
        assert len(calls) == 2

        first_progress = calls[0][0][0]
        second_progress = calls[1][0][0]

        assert first_progress == pytest.approx(50.0)
        assert second_progress == pytest.approx(75.0)

    @pytest.mark.asyncio
    async def test_file_not_found_raises_exception(self):
        """AudioTranscriptionException raised when audio file does not exist."""
        from app.shared.exceptions import AudioTranscriptionException

        settings = {
            "chunk_length_seconds": 30,
            "overlap_seconds": 1.0,
            "temp_dir": "/tmp/test_chunks",
        }

        transcriber = ChunkTranscriber(settings=settings)

        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(AudioTranscriptionException) as exc_info:
                await transcriber.transcribe(
                    audio_file="/nonexistent/audio.mp3",
                    language_in="pt",
                    language_out=None,
                    transcribe_fn=lambda *a, **k: {},
                    job_id=None,
                )

        assert "não encontrado" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Progress formula edge cases & text joining
# ---------------------------------------------------------------------------


class TestProgressFormula:

    def _make_mock_segment(self):
        seg = MagicMock()
        type(seg).__len__ = lambda self: 60_000
        return seg

    @pytest.mark.asyncio
    async def test_single_chunk_progress(self):
        """With one chunk, progress should be exactly 75.0 (25 + 50*1/1)."""
        from app.shared.audio_chunker import AudioChunk as RealAudioChunk

        settings = {
            "chunk_length_seconds": 30,
            "overlap_seconds": 1.0,
            "temp_dir": "/tmp/test_chunks",
        }

        mock_audio_segment = self._make_mock_segment()

        audio_mock = MagicMock(spec=RealAudioChunk)
        audio_mock.start_time_s = 0.0

        mock_chunker = MagicMock()
        mock_chunker.export_chunk.return_value = Path("/tmp/chunk_0.wav")

        transcribe_fn = MagicMock(return_value={
            "text": "single chunk",
            "segments": [{"start": 0, "end": 3, "text": "seg"}],
        })

        state_updater = MagicMock()
        transcriber = ChunkTranscriber(settings=settings, state=state_updater)

        with patch("pathlib.Path.exists", return_value=True):
            with patch(
                "app.shared.chunk_transcriber.AudioChunker", return_value=mock_chunker
            ):
                mock_chunker.split.return_value = [audio_mock]

                await transcriber.transcribe(
                    audio_file="/tmp/test.mp3",
                    language_in="pt",
                    language_out=None,
                    transcribe_fn=transcribe_fn,
                    job_id="job-single",
                    audio=mock_audio_segment,
                )

        calls = state_updater.set_progress.call_args_list
        assert len(calls) == 1
        # i=0 -> 25 + 50*(1/1) = 75.0
        progress_value = calls[0][0][0]
        assert progress_value == pytest.approx(75.0)

    @pytest.mark.asyncio
    async def test_no_state_updater_skips_progress(self):
        """When state is None, no set_progress calls should happen."""
        from app.shared.audio_chunker import AudioChunk as RealAudioChunk

        settings = {
            "chunk_length_seconds": 30,
            "overlap_seconds": 1.0,
            "temp_dir": "/tmp/test_chunks",
        }

        mock_audio_segment = self._make_mock_segment()

        audio_mock = MagicMock(spec=RealAudioChunk)
        audio_mock.start_time_s = 0.0

        mock_chunker = MagicMock()
        mock_chunker.export_chunk.return_value = Path("/tmp/chunk_0.wav")

        transcribe_fn = MagicMock(return_value={
            "text": "no state",
            "segments": [{"start": 0, "end": 3, "text": "seg"}],
        })

        # No state updater provided
        transcriber = ChunkTranscriber(settings=settings)

        with patch("pathlib.Path.exists", return_value=True):
            with patch(
                "app.shared.chunk_transcriber.AudioChunker", return_value=mock_chunker
            ):
                mock_chunker.split.return_value = [audio_mock]

                await transcriber.transcribe(
                    audio_file="/tmp/test.mp3",
                    language_in="pt",
                    language_out=None,
                    transcribe_fn=transcribe_fn,
                    job_id=None,
                    audio=mock_audio_segment,
                )


# ---------------------------------------------------------------------------
# Text joining across chunks
# ---------------------------------------------------------------------------


class TestTextJoining:

    def _make_mock_segment(self):
        seg = MagicMock()
        type(seg).__len__ = lambda self: 60_000
        return seg

    @pytest.mark.asyncio
    async def test_full_text_joined_with_spaces(self):
        """Full text should be space-joined from all chunk texts."""
        from app.shared.audio_chunker import AudioChunk as RealAudioChunk

        settings = {
            "chunk_length_seconds": 30,
            "overlap_seconds": 1.0,
            "temp_dir": "/tmp/test_chunks",
        }

        mock_audio_segment = self._make_mock_segment()

        chunk_mocks = []
        for offset in [0.0, 30.0]:
            cm = MagicMock(spec=RealAudioChunk)
            cm.start_time_s = offset
            chunk_mocks.append(cm)

        mock_chunker = MagicMock()
        paths_list = [Path("/tmp/chunk_0.wav"), Path("/tmp/chunk_1.wav")]
        mock_chunker.export_chunk.side_effect = lambda i, _: paths_list[i]

        texts_returned = ["primeira parte", "segunda parte"]
        idx = [0]

        def transcribe_side_effect(*args):
            t_key = "text"
            s_key = "segments"
            result = {t_key: texts_returned[idx[0]], s_key: [{"start": 0, "end": 2}]}

            idx[0] += 1
            return result

        mock_chunker = MagicMock()
        paths_list = [Path("/tmp/chunk_0.wav"), Path("/tmp/chunk_1.wav")]
        mock_chunker.export_chunk.side_effect = lambda i, _: paths_list[i]

        transcriber = ChunkTranscriber(settings=settings)

        with patch("pathlib.Path.exists", return_value=True):
            with patch(
                "app.shared.chunk_transcriber.AudioChunker", return_value=mock_chunker
            ):
                mock_chunker.split.return_value = chunk_mocks

                result = await transcriber.transcribe(
                    audio_file="/tmp/test.mp3",
                    language_in="pt",
                    language_out=None,
                    transcribe_fn=transcribe_side_effect,
                    job_id=None,
                    audio=mock_audio_segment,
                )

        assert result["text"] == "primeira parte segunda parte"
