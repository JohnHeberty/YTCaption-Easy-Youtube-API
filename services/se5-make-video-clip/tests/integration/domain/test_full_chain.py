"""Integration tests for the full 8-stage DDD chain."""
from __future__ import annotations

import asyncio
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from app.domain.job_processor import JobProcessor
from app.domain.job_stage import JobStage, StageContext, StageStatus
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


def _make_context(tmp_path: Path) -> StageContext:
    approved_dir = tmp_path / "approved" / "videos"
    approved_dir.mkdir(parents=True, exist_ok=True)
    (approved_dir / "short1.mp4").write_bytes(b"\x00" * 100)
    (approved_dir / "short2.mp4").write_bytes(b"\x00" * 100)

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    (audio_dir / "test.mp3").write_bytes(b"\x00" * 1000)

    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "final.mp4").write_bytes(b"\x00" * 5000)

    settings = {
        "temp_dir": str(tmp_path),
        "approved_dir": str(approved_dir),
        "audio_upload_dir": str(audio_dir),
        "output_dir": str(output_dir),
        "aspect_ratio": "9:16",
        "crop_position": "center",
        "subtitle_language": "pt",
    }

    ctx = StageContext(
        job_id="chain_test_01",
        query="test",
        max_shorts=5,
        aspect_ratio="9:16",
        crop_position="center",
        subtitle_language="pt-BR",
        subtitle_style="dynamic",
        settings=settings,
    )
    ctx.audio_path = audio_dir / "test.mp3"
    ctx.audio_duration = 60.0
    ctx.final_video_path = output_dir / "final.mp4"
    ctx.video_info = {"duration": 60.0, "resolution": "1080x1920", "fps": 30}
    return ctx


class MockStage(JobStage):
    """A simple mock stage that succeeds by default."""

    def __init__(self, name: str, result_data: dict | None = None) -> None:
        super().__init__(name, progress_start=0.0, progress_end=100.0)
        self._result_data = result_data or {}
        self.executed = False
        self.compensated = False

    def validate(self, context: StageContext) -> None:
        pass

    async def execute(self, context: StageContext) -> dict:
        self.executed = True
        return self._result_data

    async def compensate(self, context: StageContext) -> None:
        self.compensated = True


class FailingStage(JobStage):
    """A mock stage that always fails."""

    def __init__(self, name: str, error_msg: str = "stage failed") -> None:
        super().__init__(name, progress_start=0.0, progress_end=100.0)
        self._error_msg = error_msg

    def validate(self, context: StageContext) -> None:
        pass

    async def execute(self, context: StageContext) -> dict:
        raise RuntimeError(self._error_msg)


@pytest.mark.integration
class TestFullChainExecution:
    def test_all_8_stages_can_be_created(self):
        """All 8 stages can be instantiated and have correct names."""
        vb = MagicMock()
        stages = [
            AnalyzeAudioStage(video_builder=vb),
            LoadApprovedVideosStage(video_builder=vb),
            SelectShortsStage(),
            AssembleVideoStage(video_builder=vb),
            GenerateSubtitlesStage(
                api_client=MagicMock(),
                subtitle_generator=MagicMock(),
                vad_processor=MagicMock(),
            ),
            FinalCompositionStage(video_builder=vb),
            TrimVideoStage(video_builder=vb),
            ValidateAVSyncStage(video_builder=vb),
        ]
        names = [s.name for s in stages]
        assert names == [
            "analyze_audio",
            "load_approved",
            "select_shorts",
            "assemble_video",
            "generate_subtitles",
            "final_composition",
            "trim_video",
            "validate_av_sync",
        ]

    @pytest.mark.asyncio
    async def test_mock_chain_completes_all_stages(self):
        """A chain of mock stages all execute in order."""
        stage_names = ["stage_a", "stage_b", "stage_c", "stage_d"]
        stages = [MockStage(name) for name in stage_names]
        processor = JobProcessor(stages=stages)

        ctx = StageContext(
            job_id="mock_chain",
            query="test",
            max_shorts=5,
            aspect_ratio="9:16",
            crop_position="center",
            subtitle_language="pt",
            subtitle_style={},
            settings={},
        )

        result_ctx = await processor.process(ctx)

        assert len(processor.completed_stages) == 4
        assert processor.get_completed_stages() == stage_names
        for stage in stages:
            assert stage.executed

    @pytest.mark.asyncio
    async def test_chain_accumulates_results_in_context(self):
        """Each stage's result should be stored in context.results."""
        s1 = MockStage("s1", {"key1": "value1"})
        s2 = MockStage("s2", {"key2": "value2"})
        processor = JobProcessor(stages=[s1, s2])

        ctx = StageContext(
            job_id="result_accum",
            query="test",
            max_shorts=5,
            aspect_ratio="9:16",
            crop_position="center",
            subtitle_language="pt",
            subtitle_style={},
            settings={},
        )

        await processor.process(ctx)

        r1 = ctx.get_result("s1")
        r2 = ctx.get_result("s2")
        assert r1 is not None
        assert r1.status == StageStatus.COMPLETED
        assert r1.data == {"key1": "value1"}
        assert r2 is not None
        assert r2.data == {"key2": "value2"}

    @pytest.mark.asyncio
    async def test_stage_callback_called_for_each_stage(self):
        """The stage_callback should be invoked with processing/completed for each stage."""
        callback = AsyncMock()
        stages = [MockStage(f"s{i}") for i in range(3)]
        processor = JobProcessor(stages=stages, stage_callback=callback)

        ctx = StageContext(
            job_id="callback_test",
            query="test",
            max_shorts=5,
            aspect_ratio="9:16",
            crop_position="center",
            subtitle_language="pt",
            subtitle_style={},
            settings={},
        )

        await processor.process(ctx)

        calls = [c.args for c in callback.call_args_list]
        names_processed = [c[0] for c in calls if c[1] == "processing"]
        names_completed = [c[0] for c in calls if c[1] == "completed"]
        assert names_processed == ["s0", "s1", "s2"]
        assert names_completed == ["s0", "s1", "s2"]


@pytest.mark.integration
class TestFullChainFailure:
    @pytest.mark.asyncio
    async def test_failing_stage_stops_chain(self):
        """When a stage fails, subsequent stages should not execute."""
        s1 = MockStage("ok_stage")
        s2 = FailingStage("failing_stage", "boom")
        s3 = MockStage("never_reached")
        processor = JobProcessor(stages=[s1, s2, s3])

        ctx = StageContext(
            job_id="fail_test",
            query="test",
            max_shorts=5,
            aspect_ratio="9:16",
            crop_position="center",
            subtitle_language="pt",
            subtitle_style={},
            settings={},
        )

        with pytest.raises(Exception):
            await processor.process(ctx)

        assert s1.executed is True
        assert s3.executed is False
        assert len(processor.completed_stages) == 1

    @pytest.mark.asyncio
    async def test_failed_stage_result_recorded(self):
        """The failed stage should have a FAILED result in context."""
        stages = [MockStage("ok1"), FailingStage("fail1")]
        processor = JobProcessor(stages=stages)

        ctx = StageContext(
            job_id="fail_result",
            query="test",
            max_shorts=5,
            aspect_ratio="9:16",
            crop_position="center",
            subtitle_language="pt",
            subtitle_style={},
            settings={},
        )

        with pytest.raises(Exception):
            await processor.process(ctx)

        r = ctx.get_result("fail1")
        assert r is not None
        assert r.status == StageStatus.FAILED
        assert r.error is not None
