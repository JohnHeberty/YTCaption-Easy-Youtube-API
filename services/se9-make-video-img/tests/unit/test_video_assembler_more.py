from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.constants import CAMERA_MOVEMENT_MAP, TRANSITIONS, TRANSITION_MAP
from app.core.models import NarrationSegment, SceneSuggestion
from app.services.video_assembler import VideoAssembler, MAX_SEGMENTS, MIN_SCENE_DURATION, MAX_SCENE_DURATION


@pytest.fixture
def assembler():
    return VideoAssembler()


def test_calculate_scene_durations(assembler):
    durations = assembler._calculate_scene_durations(30.0, 3)
    assert len(durations) == 3
    assert durations[0] == pytest.approx(10.0)
    assert durations[1] == pytest.approx(10.0)
    assert durations[2] == pytest.approx(10.0)
    assert sum(durations) == pytest.approx(30.0)


def test_calculate_scene_durations_caps_at_max(assembler):
    durations = assembler._calculate_scene_durations(60.0, 100)
    assert len(durations) == MAX_SEGMENTS


def test_calculate_scene_durations_minimum_one(assembler):
    durations = assembler._calculate_scene_durations(5.0, 0)
    assert len(durations) == 1
    assert durations[0] == pytest.approx(5.0)


def test_calculate_scene_durations_remainder(assembler):
    durations = assembler._calculate_scene_durations(10.0, 3)
    assert len(durations) == 3
    assert durations[0] == pytest.approx(10.0 / 3)
    assert sum(durations) == pytest.approx(10.0)


def test_build_scene_zoom_styles_static(assembler):
    scenes = [SceneSuggestion(t=0, visual="A", camera_movement="static")]
    paths = ["/tmp/a.png"]
    result = assembler._build_scene_zoom_styles(scenes, 1, paths, "random")
    assert result == ["static"]


def test_build_scene_zoom_styles_push_in(assembler):
    scenes = [SceneSuggestion(t=0, visual="A", camera_movement="slow_push_in")]
    paths = ["/tmp/a.png"]
    result = assembler._build_scene_zoom_styles(scenes, 1, paths, "random")
    assert result == ["zoom_in"]


def test_build_scene_zoom_styles_pull_out(assembler):
    scenes = [SceneSuggestion(t=0, visual="A", camera_movement="slow_pull_out")]
    paths = ["/tmp/a.png"]
    result = assembler._build_scene_zoom_styles(scenes, 1, paths, "random")
    assert result == ["zoom_out"]


def test_build_scene_zoom_styles_default_fallback(assembler):
    result = assembler._build_scene_zoom_styles(None, 2, ["/tmp/a.png"], "zoom_in")
    assert result == ["zoom_in", "zoom_in"]


def test_build_scene_zoom_styles_random_fallback(assembler):
    result = assembler._build_scene_zoom_styles(None, 4, ["/tmp/a.png"], "random")
    assert len(result) == 4
    for s in result:
        assert s in ("zoom_in", "zoom_out")


def test_build_scene_zoom_styles_cycling(assembler):
    scenes = [
        SceneSuggestion(t=0, visual="A", camera_movement="static"),
    ]
    paths = ["/tmp/a.png", "/tmp/b.png"]
    result = assembler._build_scene_zoom_styles(scenes, 3, paths, "zoom_in")
    assert result[0] == "static"
    assert result[1] == "zoom_in"
    assert result[2] == "static"


def test_build_scene_transitions_mapped(assembler):
    scenes = [SceneSuggestion(t=0, visual="A", transition="corte seco")]
    paths = ["/tmp/a.png"]
    result = assembler._build_scene_transitions(scenes, 2, paths)
    assert result == [None]


def test_build_scene_transitions_fade_curto(assembler):
    scenes = [SceneSuggestion(t=0, visual="A", transition="fade curto")]
    paths = ["/tmp/a.png"]
    result = assembler._build_scene_transitions(scenes, 2, paths)
    assert result == ["fadeblack"]


def test_build_scene_transitions_direct_name(assembler):
    scenes = [SceneSuggestion(t=0, visual="A", transition="dissolve")]
    paths = ["/tmp/a.png"]
    result = assembler._build_scene_transitions(scenes, 2, paths)
    assert result == ["dissolve"]


def test_build_scene_transitions_random_fallback(assembler):
    result = assembler._build_scene_transitions(None, 3, ["/tmp/a.png"])
    assert len(result) == 2
    for t in result:
        assert t in TRANSITIONS


def test_build_scene_transitions_none_transitions(assembler):
    result = assembler._build_scene_transitions(None, 1, ["/tmp/a.png"])
    assert result == []


@pytest.mark.asyncio
async def test_assemble_empty_images_raises(assembler):
    with pytest.raises(ValueError, match="No images provided"):
        await assembler.assemble(
            audio_path="/tmp/audio.wav",
            image_paths=[],
            narration=[],
            output_dir="/tmp",
        )


@pytest.mark.asyncio
async def test_assemble_happy_path(assembler, tmp_path):
    audio_path = str(tmp_path / "audio.wav")
    image_path = str(tmp_path / "scene.png")
    with open(audio_path, "wb") as f:
        f.write(b"fake-audio")
    with open(image_path, "wb") as f:
        f.write(b"fake-image")

    narration = [
        NarrationSegment(t=0, text="Part 1"),
        NarrationSegment(t=10, text="Part 2"),
    ]

    with (
        patch("app.infrastructure.ffmpeg_utils.get_audio_duration", new_callable=AsyncMock, return_value=20.0),
        patch("app.infrastructure.ffmpeg_utils.create_title_card", new_callable=AsyncMock),
        patch("app.infrastructure.ffmpeg_utils.create_segment", new_callable=AsyncMock),
        patch("app.infrastructure.ffmpeg_utils.concat_segments", new_callable=AsyncMock),
        patch("app.infrastructure.ffmpeg_utils.add_audio", new_callable=AsyncMock),
        patch("app.infrastructure.ffmpeg_utils.trim_to_duration", new_callable=AsyncMock),
        patch.object(assembler, "_pad_audio_start", new_callable=AsyncMock),
    ):
        result = await assembler.assemble(
            audio_path=audio_path,
            image_paths=[image_path],
            narration=narration,
            output_dir=str(tmp_path),
            job_id="test_job",
            hook_text="Hook",
        )

    assert result.endswith("test_job_final.mp4")


@pytest.mark.asyncio
async def test_assemble_no_hook_skips_title_card(assembler, tmp_path):
    audio_path = str(tmp_path / "audio.wav")
    image_path = str(tmp_path / "scene.png")
    with open(audio_path, "wb") as f:
        f.write(b"fake-audio")
    with open(image_path, "wb") as f:
        f.write(b"fake-image")

    narration = [NarrationSegment(t=0, text="Hello")]

    with (
        patch("app.infrastructure.ffmpeg_utils.get_audio_duration", new_callable=AsyncMock, return_value=5.0),
        patch("app.infrastructure.ffmpeg_utils.create_title_card", new_callable=AsyncMock) as mock_title,
        patch("app.infrastructure.ffmpeg_utils.create_segment", new_callable=AsyncMock),
        patch("app.infrastructure.ffmpeg_utils.concat_segments", new_callable=AsyncMock),
        patch("app.infrastructure.ffmpeg_utils.add_audio", new_callable=AsyncMock),
        patch("app.infrastructure.ffmpeg_utils.trim_to_duration", new_callable=AsyncMock),
        patch.object(assembler, "_pad_audio_start", new_callable=AsyncMock),
    ):
        await assembler.assemble(
            audio_path=audio_path,
            image_paths=[image_path],
            narration=narration,
            output_dir=str(tmp_path),
            hook_text="",
        )
        mock_title.assert_not_called()


@pytest.mark.asyncio
async def test_assemble_passes_zoom_style_to_segments(assembler, tmp_path):
    audio_path = str(tmp_path / "audio.wav")
    image_path = str(tmp_path / "scene.png")
    with open(audio_path, "wb") as f:
        f.write(b"audio")
    with open(image_path, "wb") as f:
        f.write(b"image")

    narration = [NarrationSegment(t=0, text="Hello")]

    with (
        patch("app.infrastructure.ffmpeg_utils.get_audio_duration", new_callable=AsyncMock, return_value=5.0),
        patch("app.infrastructure.ffmpeg_utils.create_segment", new_callable=AsyncMock) as mock_seg,
        patch("app.infrastructure.ffmpeg_utils.concat_segments", new_callable=AsyncMock),
        patch("app.infrastructure.ffmpeg_utils.add_audio", new_callable=AsyncMock),
        patch("app.infrastructure.ffmpeg_utils.trim_to_duration", new_callable=AsyncMock),
        patch.object(assembler, "_pad_audio_start", new_callable=AsyncMock),
    ):
        await assembler.assemble(
            audio_path=audio_path,
            image_paths=[image_path],
            narration=narration,
            output_dir=str(tmp_path),
            zoom_style="zoom_out",
        )

    call_kwargs = mock_seg.call_args.kwargs
    assert "zoom_style" in call_kwargs
