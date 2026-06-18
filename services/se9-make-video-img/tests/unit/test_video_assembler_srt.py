"""Unit tests for video assembler SRT generation."""
import os
import tempfile
import pytest
from app.services.video_assembler import VideoAssembler
from app.core.models import OnScreenText


@pytest.fixture
def assembler():
    return VideoAssembler()


def test_format_srt_time(assembler):
    assert assembler._format_srt_time(0) == "00:00:00,000"
    assert assembler._format_srt_time(65.5) == "00:01:05,500"
    assert assembler._format_srt_time(3661.123) == "01:01:01,123"


def test_generate_srt(assembler):
    with tempfile.TemporaryDirectory() as tmpdir:
        srt_path = os.path.join(tmpdir, "test.srt")
        on_screen_text = [
            OnScreenText(t=0, text="First subtitle"),
            OnScreenText(t=5, text="Second subtitle"),
        ]
        assembler._generate_srt(on_screen_text, srt_path)
        assert os.path.exists(srt_path)
        with open(srt_path) as f:
            content = f.read()
        assert "First subtitle" in content
        assert "Second subtitle" in content
        assert "00:00:00,000" in content


def test_generate_srt_empty(assembler):
    with tempfile.TemporaryDirectory() as tmpdir:
        srt_path = os.path.join(tmpdir, "empty.srt")
        assembler._generate_srt([], srt_path)
        assert os.path.exists(srt_path)


def test_calculate_scene_durations(assembler):
    from app.core.models import NarrationSegment
    narration = [
        NarrationSegment(t=0, text="Part 1"),
        NarrationSegment(t=5, text="Part 2"),
        NarrationSegment(t=10, text="Part 3"),
    ]
    durations = assembler._calculate_scene_durations(narration, audio_duration=15.0)
    assert len(durations) == 3
    assert durations[0] == 5.0
    assert durations[1] == 5.0
    assert durations[2] == 5.0
