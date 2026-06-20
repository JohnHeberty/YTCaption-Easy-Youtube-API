"""Unit tests for video assembler scene duration calculation."""
import pytest
from app.services.video_assembler import VideoAssembler
from app.core.models import NarrationSegment


@pytest.fixture
def assembler():
    return VideoAssembler()


def test_calculate_scene_durations_equal_split(assembler):
    """Audio divided equally among requested scenes."""
    durations = assembler._calculate_scene_durations(audio_duration=30.0, num_scenes_needed=6)
    assert len(durations) == 6
    assert sum(durations) == pytest.approx(30.0, abs=0.01)


def test_calculate_scene_durations_single_scene(assembler):
    """Single scene covers entire audio."""
    durations = assembler._calculate_scene_durations(audio_duration=120.0, num_scenes_needed=1)
    assert len(durations) == 1
    assert durations[0] == pytest.approx(120.0)


def test_calculate_scene_durations_caps_at_12(assembler):
    """Many requested scenes get capped at 12."""
    durations = assembler._calculate_scene_durations(audio_duration=200.0, num_scenes_needed=25)
    assert len(durations) == 12
    assert sum(durations) == pytest.approx(200.0, abs=0.01)


def test_calculate_scene_durations_min_one(assembler):
    """num_scenes_needed=0 defaults to 1."""
    durations = assembler._calculate_scene_durations(audio_duration=10.0, num_scenes_needed=0)
    assert len(durations) == 1
