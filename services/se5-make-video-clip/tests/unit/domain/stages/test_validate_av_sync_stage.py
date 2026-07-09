"""Unit tests for ValidateAVSyncStage."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.domain.stages.validate_av_sync_stage import ValidateAVSyncStage
from app.domain.job_stage import StageContext


def _make_context(tmp_path: Path, final_video: Path | None = None) -> StageContext:
    settings = {"temp_dir": str(tmp_path), "aspect_ratio": "9:16"}
    ctx = StageContext(
        job_id="test_avsync_01",
        query="test",
        max_shorts=10,
        aspect_ratio="9:16",
        crop_position="center",
        subtitle_language="pt",
        subtitle_style="dynamic",
        settings=settings,
    )
    ctx.audio_duration = 60.0
    ctx.audio_path = tmp_path / "audio.mp3"
    ctx.audio_path.write_bytes(b"\x00" * 100)
    ctx.final_video_path = final_video or tmp_path / "final.mp4"
    ctx.selected_shorts = []
    ctx.temp_video_path = tmp_path / "temp.mp4"
    ctx.video_info = {"duration": 62.0, "width": 1080, "height": 1920, "fps": 30}
    ctx.file_size = 1024 * 1024 * 10
    return ctx


class TestValidateAVSyncStage:
    def test_validate_does_not_raise_for_valid_video(self, tmp_path):
        """validate() should pass (returns None) when video exists."""
        video = tmp_path / "final.mp4"
        video.write_bytes(b"\x00" * 100)

        ctx = _make_context(tmp_path, final_video=video)
        stage = ValidateAVSyncStage(video_builder=MagicMock())
        result = stage.validate(ctx)
        assert result is None  # validate returns None on success

    def test_validate_passes_when_video_missing(self, tmp_path):
        """validate() is non-critical — should pass even if file missing."""
        ctx = _make_context(tmp_path, final_video=None)
        ctx.final_video_path = tmp_path / "nonexistent.mp4"

        stage = ValidateAVSyncStage(video_builder=MagicMock())
        result = stage.validate(ctx)
        assert result is None  # non-critical, passes

    def test_execute_skips_when_no_files(self, tmp_path):
        """execute() should return skipped when files missing."""
        ctx = _make_context(tmp_path, final_video=None)
        ctx.final_video_path = None

        stage = ValidateAVSyncStage(video_builder=MagicMock())
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(stage.execute(ctx))
        assert result["skipped"] is True
