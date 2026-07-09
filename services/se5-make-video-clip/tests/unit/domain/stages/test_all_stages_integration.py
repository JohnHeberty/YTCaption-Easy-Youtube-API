"""Integration tests for all 8 stages."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.domain.stages import (
    AnalyzeAudioStage,
    LoadApprovedVideosStage,
    SelectShortsStage,
    AssembleVideoStage,
    GenerateSubtitlesStage,
    FinalCompositionStage,
    TrimVideoStage,
    ValidateAVSyncStage,
)
from app.domain.job_stage import StageContext


class TestAllStagesIntegration:
    def test_stage_names_are_correct(self):
        """Each stage should have the expected name."""
        vb = MagicMock()
        stages = [
            ("analyze_audio", AnalyzeAudioStage(video_builder=vb)),
            ("load_approved", LoadApprovedVideosStage(video_builder=vb)),
            ("select_shorts", SelectShortsStage()),
            ("assemble_video", AssembleVideoStage(video_builder=vb)),
            ("generate_subtitles", GenerateSubtitlesStage(api_client=MagicMock(), subtitle_generator=MagicMock(), vad_processor=MagicMock())),
            ("final_composition", FinalCompositionStage(video_builder=vb)),
            ("trim_video", TrimVideoStage(video_builder=vb)),
            ("validate_av_sync", ValidateAVSyncStage(video_builder=vb)),
        ]
        for name, stage in stages:
            assert stage.name == name, f"Stage {name} has wrong name: {stage.name}"

    def test_stage_count(self):
        """Should have exactly 8 stages."""
        vb = MagicMock()
        stage_count = len([
            AnalyzeAudioStage(video_builder=vb),
            LoadApprovedVideosStage(video_builder=vb),
            SelectShortsStage(),
            AssembleVideoStage(video_builder=vb),
            GenerateSubtitlesStage(api_client=MagicMock(), subtitle_generator=MagicMock(), vad_processor=MagicMock()),
            FinalCompositionStage(video_builder=vb),
            TrimVideoStage(video_builder=vb),
            ValidateAVSyncStage(video_builder=vb),
        ])
        assert stage_count == 8

    def test_all_stages_have_progress_bounds(self):
        """All stages should define progress_start and progress_end."""
        vb = MagicMock()
        stages = [
            AnalyzeAudioStage(video_builder=vb),
            LoadApprovedVideosStage(video_builder=vb),
            SelectShortsStage(),
            AssembleVideoStage(video_builder=vb),
            GenerateSubtitlesStage(api_client=MagicMock(), subtitle_generator=MagicMock(), vad_processor=MagicMock()),
            FinalCompositionStage(video_builder=vb),
            TrimVideoStage(video_builder=vb),
            ValidateAVSyncStage(video_builder=vb),
        ]
        for stage in stages:
            assert stage.progress_start >= 0
            assert stage.progress_end <= 100
            assert stage.progress_end > stage.progress_start
