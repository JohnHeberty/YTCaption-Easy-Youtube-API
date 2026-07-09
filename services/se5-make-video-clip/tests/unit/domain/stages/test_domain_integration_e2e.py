"""E2E tests for domain_integration (LoadApproved + ValidateAVSync path)."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.shared.domain_integration import DomainJobProcessor
from app.domain.stages import LoadApprovedVideosStage, ValidateAVSyncStage


class TestDomainIntegrationE2E:
    def test_create_stages_includes_new_stages(self, tmp_path):
        """DomainDrivenProcessor._create_stages() should include LoadApproved and ValidateAVSync."""
        processor = DomainJobProcessor.__new__(DomainJobProcessor)
        processor.video_builder = MagicMock()
        processor.api_client = MagicMock()
        processor.shorts_cache = MagicMock()
        processor.video_validator = MagicMock()
        processor.blacklist = MagicMock()
        processor.subtitle_gen = MagicMock()
        processor.settings = {"temp_dir": str(tmp_path), "aspect_ratio": "9:16"}

        stages = processor._create_stages()

        stage_names = [s.name for s in stages]
        assert "load_approved" in stage_names
        assert "validate_av_sync" in stage_names
        assert "fetch_shorts" not in stage_names
        assert "download_shorts" not in stage_names

    def test_stage_order_starts_with_analyze_audio(self, tmp_path):
        """First stage should be analyze_audio."""
        processor = DomainJobProcessor.__new__(DomainJobProcessor)
        processor.video_builder = MagicMock()
        processor.api_client = MagicMock()
        processor.shorts_cache = MagicMock()
        processor.video_validator = MagicMock()
        processor.blacklist = MagicMock()
        processor.subtitle_gen = MagicMock()
        processor.settings = {"temp_dir": str(tmp_path), "aspect_ratio": "9:16"}

        stages = processor._create_stages()
        assert stages[0].name == "analyze_audio"

    def test_stage_order_ends_with_validate_av_sync(self, tmp_path):
        """Last stage should be validate_av_sync."""
        processor = DomainJobProcessor.__new__(DomainJobProcessor)
        processor.video_builder = MagicMock()
        processor.api_client = MagicMock()
        processor.shorts_cache = MagicMock()
        processor.video_validator = MagicMock()
        processor.blacklist = MagicMock()
        processor.subtitle_gen = MagicMock()
        processor.settings = {"temp_dir": str(tmp_path), "aspect_ratio": "9:16"}

        stages = processor._create_stages()
        assert stages[-1].name == "validate_av_sync"

    def test_stage_count(self, tmp_path):
        """Should have 8 stages total."""
        processor = DomainJobProcessor.__new__(DomainJobProcessor)
        processor.video_builder = MagicMock()
        processor.api_client = MagicMock()
        processor.shorts_cache = MagicMock()
        processor.video_validator = MagicMock()
        processor.blacklist = MagicMock()
        processor.subtitle_gen = MagicMock()
        processor.settings = {"temp_dir": str(tmp_path), "aspect_ratio": "9:16"}

        stages = processor._create_stages()
        assert len(stages) == 8
