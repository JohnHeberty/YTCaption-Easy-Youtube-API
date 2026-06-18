"""Unit tests for audio text chunking."""
import pytest
from app.services.audio_generator import AudioGenerator
from app.core.constants import CHATTERBOX_MAX_CHARS


@pytest.fixture
def generator():
    return AudioGenerator()


def test_chunk_text_short(generator):
    text = "This is a short text."
    chunks = generator._chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_at_limit(generator):
    text = "x" * CHATTERBOX_MAX_CHARS
    chunks = generator._chunk_text(text)
    assert len(chunks) == 1


def test_chunk_text_over_limit(generator):
    text = "x" * (CHATTERBOX_MAX_CHARS + 100)
    chunks = generator._chunk_text(text)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk) <= CHATTERBOX_MAX_CHARS


def test_chunk_text_paragraphs(generator):
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    chunks = generator._chunk_text(text)
    assert len(chunks) >= 1


def test_chunk_text_long_paragraph(generator):
    text = "Word " * 2000
    chunks = generator._chunk_text(text)
    assert len(chunks) >= 1
    for chunk in chunks:
        assert len(chunk) <= CHATTERBOX_MAX_CHARS


def test_concatenate_narration(generator):
    from app.core.models import NarrationSegment
    segments = [
        NarrationSegment(t=10, text="Second part"),
        NarrationSegment(t=0, text="First part"),
    ]
    result = generator._concatenate_narration(segments)
    assert result == "First part Second part"


def test_concatenate_narration_empty(generator):
    result = generator._concatenate_narration([])
    assert result == ""


def test_chunk_text_multiple_chunks(generator):
    paragraphs = [f"Paragraph {i}. {'Word ' * 500}" for i in range(5)]
    text = "\n\n".join(paragraphs)
    chunks = generator._chunk_text(text)
    assert len(chunks) >= 2
