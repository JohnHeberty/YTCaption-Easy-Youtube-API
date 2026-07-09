"""Unit tests for LoadApprovedVideosStage."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.domain.stages.load_approved_stage import LoadApprovedVideosStage
from app.domain.job_stage import StageContext
from app.shared.exceptions import VideoProcessingException, ErrorCode


def _make_context(tmp_path: Path, job_id: str = "test_load_01") -> StageContext:
    approved_dir = tmp_path / "approved" / "videos"
    approved_dir.mkdir(parents=True, exist_ok=True)
    settings = {
        "temp_dir": str(tmp_path),
        "aspect_ratio": "9:16",
        "crop_position": "center",
        "approved_dir": str(approved_dir),
    }
    return StageContext(
        job_id=job_id,
        query="test",
        max_shorts=10,
        aspect_ratio="9:16",
        crop_position="center",
        subtitle_language="pt",
        subtitle_style="dynamic",
        settings=settings,
    )


class TestLoadApprovedVideosStage:
    def test_validate_passes_with_videos(self, tmp_path):
        """validate() should pass silently if approved dir has videos."""
        ctx = _make_context(tmp_path)
        (Path(ctx.settings["approved_dir"]) / "a.mp4").write_bytes(b"\x00" * 100)

        stage = LoadApprovedVideosStage(video_builder=MagicMock())
        result = stage.validate(ctx)
        assert result is None  # validate returns None on success

    def test_no_approved_dir_raises(self, tmp_path):
        """Missing directory should raise."""
        ctx = _make_context(tmp_path)
        ctx.settings["approved_dir"] = str(tmp_path / "nonexistent")

        stage = LoadApprovedVideosStage(video_builder=MagicMock())
        with pytest.raises(VideoProcessingException) as exc_info:
            stage.validate(ctx)
        assert exc_info.value.error_code == ErrorCode.NO_SHORTS_FOUND

    def test_empty_approved_dir_raises(self, tmp_path):
        """Empty directory should raise."""
        empty_dir = tmp_path / "empty_approved"
        empty_dir.mkdir(parents=True)
        ctx = _make_context(tmp_path)
        ctx.settings["approved_dir"] = str(empty_dir)

        stage = LoadApprovedVideosStage(video_builder=MagicMock())
        with pytest.raises(VideoProcessingException) as exc_info:
            stage.validate(ctx)
        assert exc_info.value.error_code == ErrorCode.NO_SHORTS_FOUND

    def test_validate_fails_when_no_mp4_files(self, tmp_path):
        """Directory with no .mp4 files should raise."""
        non_mp4_dir = tmp_path / "no_mp4"
        non_mp4_dir.mkdir(parents=True)
        (non_mp4_dir / "file.txt").write_text("not a video")

        ctx = _make_context(tmp_path)
        ctx.settings["approved_dir"] = str(non_mp4_dir)

        stage = LoadApprovedVideosStage(video_builder=MagicMock())
        with pytest.raises(VideoProcessingException):
            stage.validate(ctx)
