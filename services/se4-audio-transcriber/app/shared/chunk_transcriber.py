import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional

from pydub import AudioSegment

from .audio_chunker import AudioChunker
from ..shared.exceptions import AudioTranscriptionException

logger = logging.getLogger(__name__)


class ChunkTranscriber:
    """Orchestrate multi-chunk transcription for long audio files.

    Accepts a callable *transcribe_fn* that performs the actual transcription
    of individual chunks, keeping this class decoupled from any specific
    transcription engine (Dependency Inversion Principle).
    """

    def __init__(self, settings: Dict[str, any], state=None):
        self.settings = settings or {}
        self.state = state  # JobStateUpdater – may be None when no job tracking

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def transcribe(
        self,
        audio_file: str,
        language_in: str,
        language_out: Optional[str],
        transcribe_fn: Callable[[str, str, Optional[str]], Dict[str, any]],
        job_id: Optional[str] = None,
        audio: AudioSegment | None = None,
    ) -> Dict[str, any]:
        """Orchestrate chunking + transcription loop + segment merge.

        Args:
            audio_file: Path to the source audio file.
            language_in: Input language for transcription ("auto" for detection).
            language_out: Output language for translation (None = transcribe only).
            transcribe_fn: Callable(chunk_path, lang_in, lang_out) -> dict with
                ``'text'`` and ``'segments'`` keys.  Responsible for the actual
                engine-level transcription of a single chunk.
            job_id: Optional job identifier for progress tracking via *state*.
            audio: Pre-loaded AudioSegment (avoids re-reading from disk).

        Returns:
            dict with ``'text'`` and ``'segments'`` in Whisper format.
        """
        try:
            audio_path = Path(audio_file)
            if not audio_path.exists():
                raise AudioTranscriptionException(
                    f"Arquivo de áudio não encontrado para chunking: {audio_file}"
                )

            # Load audio if not provided
            if audio is None:
                logger.info(f"Carregando áudio para chunking (ChunkTranscriber): {audio_file}")
                try:
                    audio = AudioSegment.from_file(str(audio_path))
                except Exception as e:
                    raise AudioTranscriptionException(
                        f"Erro ao carregar arquivo de áudio com pydub: {str(e)}"
                    )

            duration_seconds = len(audio) / 1000.0

            # Chunking settings
            chunk_length_seconds = self.settings.get("chunk_length_seconds", 30)
            overlap_seconds = self.settings.get("chunk_overlap_seconds", 1.0)

            logger.info(
                f"Processando áudio de {duration_seconds:.1f}s em chunks "
                f"de {chunk_length_seconds}s com overlap de {overlap_seconds}s"
            )

            # AudioChunker: split + temp file management
            chunker = AudioChunker(
                temp_dir=self.settings.get("temp_dir", "./temp"),
                chunk_length_seconds=chunk_length_seconds,
                overlap_seconds=overlap_seconds,
            )

            chunks = chunker.split(audio)
            logger.info(f"Áudio dividido em {len(chunks)} chunks")

            # Transcribe each chunk via the injected callable
            all_segments: List[Dict[str, any]] = []
            full_text_parts: List[str] = []

            for i, audio_chunk in enumerate(chunks):
                chunk_file = chunker.export_chunk(i, audio_chunk)

                logger.info(
                    f"Processando chunk {i + 1}/{len(chunks)} "
                    f"(offset: {audio_chunk.start_time_s:.1f}s)"
                )

                # Transcribe or translate the chunk through the injected function
                chunk_result = transcribe_fn(str(chunk_file), language_in, language_out)

                # Adjust segment timestamps with chunk offset
                for segment in chunk_result["segments"]:
                    adjusted_segment = segment.copy()
                    adjusted_segment["start"] += audio_chunk.start_time_s
                    adjusted_segment["end"] += audio_chunk.start_time_s
                    all_segments.append(adjusted_segment)

                full_text_parts.append(chunk_result["text"])

                # Cleanup temp file via chunker
                chunker.cleanup_chunk(chunk_file)

                # Progress update: 25% initial + 50% during chunks
                if job_id and self.state:
                    progress = 25.0 + (50.0 * (i + 1) / len(chunks))
                    self.state.set_progress(progress, job_id)

            # Merge overlapping segments to remove duplicates at overlap boundaries
            merged_segments = self._merge_overlapping_segments(all_segments, overlap_seconds)

            full_text = " ".join(full_text_parts)

            logger.info(f"Chunking concluído: {len(merged_segments)} segmentos finais")

            return {
                "text": full_text,
                "segments": merged_segments,
            }

        except Exception as e:
            logger.error(f"Erro no chunking (ChunkTranscriber): {e}")
            raise AudioTranscriptionException(f"Falha no chunking: {str(e)}")

    # ------------------------------------------------------------------
    # Segment merge & similarity helpers  (moved from processor.py)
    # ------------------------------------------------------------------

    def _merge_overlapping_segments(
        self, segments: List[Dict[str, any]], overlap_seconds: float
    ) -> List[Dict[str, any]]:
        """Merge overlapping segments by removing near-duplicate text.

        Args:
            segments: List of segment dicts with ``'start'``, ``'end'`` and ``'text'`` keys.
            overlap_seconds: Duration of the overlap window in seconds.

        Returns:
            Merged list without duplicate-overlap segments.
        """
        if not segments:
            return []

        sorted_segments = sorted(segments, key=lambda s: s["start"])

        merged = []
        for segment in sorted_segments:
            # No overlap with the last added segment – keep it as-is
            if not merged or segment["start"] >= merged[-1]["end"]:
                merged.append(segment)
            else:
                # Overlap detected – check whether text is duplicated
                last_text = merged[-1]["text"].strip()
                current_text = segment["text"].strip()

                if self._text_similarity(last_text, current_text) > 0.8:
                    # Duplicate text in overlap region – extend end time only
                    if segment["end"] > merged[-1]["end"]:
                        merged[-1]["end"] = segment["end"]
                else:
                    # Different content – keep both segments
                    merged.append(segment)

        return merged

    @staticmethod
    def _text_similarity(text1: str, text2: str) -> float:
        """Calculate simple word-based Jaccard similarity between two texts (0.0-1.0)."""
        if not text1 or not text2:
            return 0.0

        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)
