from __future__ import annotations

from pathlib import Path

from pydub import AudioSegment


class AudioChunk:
    """Represents a single audio chunk with metadata."""

    def __init__(self, audio: AudioSegment, start_time_s: float, number: int) -> None:
        self.audio = audio
        self.start_time_s = start_time_s
        self.number = number


class AudioChunker:
    """Split an audio file into overlapping chunks for parallel transcription.

    Responsibilities (pure audio splitting):
      - Calculate chunk boundaries from duration / size settings
      - Split a loaded AudioSegment into overlapping slices
      - Export each slice to a temporary WAV file
      - Clean up temporary chunk files after processing

    The caller is responsible for transcribing each chunk and merging results.
    """

    def __init__(self, temp_dir: str = "./data/temp", chunk_length_seconds: float = 30, overlap_seconds: float = 1.0) -> None:
        self.temp_dir = Path(temp_dir)
        self.chunk_length_ms = int(chunk_length_seconds * 1000)
        self.overlap_ms = int(overlap_seconds * 1000)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def split(self, audio: AudioSegment) -> list[AudioChunk]:
        """Split a loaded ``AudioSegment`` into overlapping chunks.

        Returns a list of :class:`AudioChunk` instances ordered by position.
        """
        duration_ms = len(audio)
        step_ms = self.chunk_length_ms - self.overlap_ms

        if step_ms <= 0:
            raise ValueError(
                f"chunk_length_seconds must be greater than overlap_seconds "
                f"(got {self.chunk_length_ms / 1000}s vs {self.overlap_ms / 1000}s)"
            )

        chunks: List[AudioChunk] = []
        current_position = 0
        chunk_number = 0

        while current_position < duration_ms:
            end_position = min(current_position + self.chunk_length_ms, duration_ms)
            chunk_audio = audio[current_position:end_position]
            start_time_s = current_position / 1000.0

            chunks.append(AudioChunk(
                audio=chunk_audio,
                start_time_s=start_time_s,
                number=chunk_number,
            ))

            chunk_number += 1
            current_position += step_ms

        return chunks

    def export_chunk(self, index: int, chunk: AudioChunk) -> Path:
        """Export a single ``AudioChunk`` to a temporary WAV file.

        The temp directory is created if it does not exist.
        Returns the absolute path of the exported file.
        """
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        chunk_file = self.temp_dir / f"chunk_{index}.wav"
        chunk.audio.export(chunk_file, format="wav")
        return chunk_file

    def cleanup_chunk(self, path: Path) -> None:
        """Remove a single temporary chunk file."""
        if path.exists():
            path.unlink()

    @staticmethod
    def should_chunk(duration_seconds: float, min_duration_for_chunks: int = 300) -> bool:
        """Return ``True`` when the audio is long enough to warrant chunking.

        Default threshold is 5 minutes (300 s). Override via *min_duration_for_chunks*.
        """
        return duration_seconds > min_duration_for_chunks
