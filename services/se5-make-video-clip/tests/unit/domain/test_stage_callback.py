"""Unit tests for _on_stage_update callback and JobProcessor stage_callback."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.core.models import MakeVideoJob, StageInfo
from app.shared.domain_integration import DomainJobProcessor
from app.domain.job_processor import JobProcessor
from app.domain.job_stage import JobStage, StageContext, StageResult, StageStatus


def _make_processor(tmp_path) -> DomainJobProcessor:
    """Create a DomainJobProcessor with mocked dependencies."""
    proc = DomainJobProcessor.__new__(DomainJobProcessor)
    proc.redis_store = MagicMock()
    proc.api_client = MagicMock()
    proc.video_builder = MagicMock()
    proc.shorts_cache = MagicMock()
    proc.video_validator = MagicMock()
    proc.blacklist = MagicMock()
    proc.subtitle_gen = MagicMock()
    proc.settings = {"temp_dir": str(tmp_path), "aspect_ratio": "9:16"}
    proc.event_publisher = None
    proc._current_job = None
    proc.stages = proc._create_stages()
    proc.processor = JobProcessor(
        stages=proc.stages,
        stage_callback=proc._on_stage_update,
    )
    return proc


def _make_job() -> MakeVideoJob:
    """Create a MakeVideoJob with pre-created stages."""
    return MakeVideoJob.create_new(
        audio_file="test.ogg",
        max_shorts=5,
        subtitle_language="pt",
    )


# ─── _on_stage_update unit tests ────────────────────────────────────────────


class TestOnStageUpdateCreatesStageInfo:
    """_on_stage_update should create StageInfo when stage not in job.stages."""

    @pytest.mark.asyncio
    async def test_creates_new_stage_info(self, tmp_path):
        proc = _make_processor(tmp_path)
        job = _make_job()
        proc._current_job = job

        # Remove a stage to simulate first-time creation
        del job.stages["analyze_audio"]

        await proc._on_stage_update("analyze_audio", "processing", 0.0, 0.0, None)

        assert "analyze_audio" in job.stages
        info = job.stages["analyze_audio"]
        assert isinstance(info, StageInfo)
        assert info.status.value == "processing"

    @pytest.mark.asyncio
    async def test_display_name_mapped(self, tmp_path):
        proc = _make_processor(tmp_path)
        job = _make_job()
        proc._current_job = job

        del job.stages["assemble_video"]
        await proc._on_stage_update("assemble_video", "processing", 0.0, 0.0, None)

        assert job.stages["assemble_video"].display_name == "Assembling video"

    @pytest.mark.asyncio
    async def test_unknown_stage_uses_name_as_display(self, tmp_path):
        proc = _make_processor(tmp_path)
        job = _make_job()
        proc._current_job = job

        await proc._on_stage_update("unknown_stage", "processing", 0.0, 0.0, None)

        assert job.stages["unknown_stage"].display_name == "unknown_stage"


class TestOnStageUpdateStatusTransitions:
    """_on_stage_update should handle all status values correctly."""

    @pytest.mark.asyncio
    async def test_processing_calls_start(self, tmp_path):
        proc = _make_processor(tmp_path)
        job = _make_job()
        proc._current_job = job

        await proc._on_stage_update("analyze_audio", "processing", 0.0, 0.0, None)

        info = job.stages["analyze_audio"]
        assert info.status.value == "processing"
        assert info.started_at is not None

    @pytest.mark.asyncio
    async def test_completed_calls_complete(self, tmp_path):
        proc = _make_processor(tmp_path)
        job = _make_job()
        proc._current_job = job

        await proc._on_stage_update("analyze_audio", "completed", 100.0, 1.5, None)

        info = job.stages["analyze_audio"]
        assert info.status.value == "completed"
        assert info.completed_at is not None
        assert info.progress == 100.0

    @pytest.mark.asyncio
    async def test_failed_calls_fail(self, tmp_path):
        proc = _make_processor(tmp_path)
        job = _make_job()
        proc._current_job = job

        await proc._on_stage_update("assemble_video", "failed", 50.0, 2.0, "FFmpeg error")

        info = job.stages["assemble_video"]
        assert info.status.value == "failed"
        assert info.error_message == "FFmpeg error"

    @pytest.mark.asyncio
    async def test_failed_without_error_msg(self, tmp_path):
        proc = _make_processor(tmp_path)
        job = _make_job()
        proc._current_job = job

        await proc._on_stage_update("assemble_video", "failed", 50.0, 2.0, None)

        info = job.stages["assemble_video"]
        assert info.status.value == "failed"
        assert info.error_message == "Unknown error"

    @pytest.mark.asyncio
    async def test_progress_updated(self, tmp_path):
        proc = _make_processor(tmp_path)
        job = _make_job()
        proc._current_job = job

        await proc._on_stage_update("assemble_video", "processing", 45.0, 0.0, None)

        assert job.stages["assemble_video"].progress == 45.0


class TestOnStageUpdateSavesJob:
    """_on_stage_update should persist to Redis after each update."""

    @pytest.mark.asyncio
    async def test_save_job_called(self, tmp_path):
        proc = _make_processor(tmp_path)
        job = _make_job()
        proc._current_job = job

        await proc._on_stage_update("analyze_audio", "processing", 0.0, 0.0, None)

        proc.redis_store.save_job.assert_called_once_with(job)

    @pytest.mark.asyncio
    async def test_save_job_called_on_completed(self, tmp_path):
        proc = _make_processor(tmp_path)
        job = _make_job()
        proc._current_job = job

        await proc._on_stage_update("analyze_audio", "completed", 100.0, 1.0, None)

        proc.redis_store.save_job.assert_called_once_with(job)


class TestOnStageUpdateErrorHandling:
    """_on_stage_update should handle errors gracefully."""

    @pytest.mark.asyncio
    async def test_no_job_does_nothing(self, tmp_path):
        proc = _make_processor(tmp_path)
        proc._current_job = None

        # Should not raise
        await proc._on_stage_update("analyze_audio", "processing", 0.0, 0.0, None)

        proc.redis_store.save_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_job_error_does_not_raise(self, tmp_path):
        proc = _make_processor(tmp_path)
        job = _make_job()
        proc._current_job = job
        proc.redis_store.save_job.side_effect = RuntimeError("Redis down")

        # Should not raise even if save fails
        await proc._on_stage_update("analyze_audio", "processing", 0.0, 0.0, None)

        # StageInfo was still updated in memory
        assert job.stages["analyze_audio"].status.value == "processing"


# ─── JobProcessor stage_callback integration tests ───────────────────────────


class FakeStage(JobStage):
    """Minimal stage for testing JobProcessor callback invocation."""

    def __init__(self, name: str, duration: float = 0.1):
        super().__init__(name=name, progress_start=0, progress_end=100)
        self._duration = duration

    def validate(self, context: StageContext) -> None:
        pass

    async def execute(self, context: StageContext) -> dict:
        return {"done": True}


class FailingStage(JobStage):
    """Stage that always fails."""

    def __init__(self, name: str):
        super().__init__(name=name, progress_start=0, progress_end=100)

    def validate(self, context: StageContext) -> None:
        pass

    async def execute(self, context: StageContext) -> dict:
        raise RuntimeError("Stage failed intentionally")


class TestJobProcessorCallback:
    """JobProcessor should call stage_callback after each stage."""

    @pytest.mark.asyncio
    async def test_callback_called_per_stage(self):
        callback = AsyncMock()
        stages = [FakeStage("s1"), FakeStage("s2"), FakeStage("s3")]
        processor = JobProcessor(stages=stages, stage_callback=callback)

        context = StageContext(
            job_id="test", query="q", max_shorts=5,
            aspect_ratio="9:16", crop_position="center",
            subtitle_language="pt", subtitle_style={}, settings={},
        )

        await processor.process(context)

        # processing + completed for each stage = 6 calls
        assert callback.call_count == 6
        calls = [c.args for c in callback.call_args_list]
        # Stage s1: processing then completed
        assert calls[0] == ("s1", "processing", 0.0, 0.0, None)
        assert calls[1][0] == "s1"
        assert calls[1][1] == "completed"
        assert calls[1][4] is None
        # Stage s2: processing then completed
        assert calls[2] == ("s2", "processing", 0.0, 0.0, None)
        assert calls[3][0] == "s2"
        assert calls[3][1] == "completed"
        # Stage s3: processing then completed
        assert calls[4] == ("s3", "processing", 0.0, 0.0, None)
        assert calls[5][0] == "s3"
        assert calls[5][1] == "completed"

    @pytest.mark.asyncio
    async def test_callback_on_failure(self):
        callback = AsyncMock()
        stages = [FakeStage("ok"), FailingStage("bad")]
        processor = JobProcessor(stages=stages, stage_callback=callback)

        context = StageContext(
            job_id="test", query="q", max_shorts=5,
            aspect_ratio="9:16", crop_position="center",
            subtitle_language="pt", subtitle_style={}, settings={},
        )

        with pytest.raises(Exception):
            await processor.process(context)

        # ok: processing+completed, bad: processing+failed
        assert callback.call_count == 4
        calls = [c.args for c in callback.call_args_list]
        assert calls[0] == ("ok", "processing", 0.0, 0.0, None)
        assert calls[1][0] == "ok"
        assert calls[1][1] == "completed"
        assert calls[2] == ("bad", "processing", 0.0, 0.0, None)
        assert calls[3][0] == "bad"
        assert calls[3][1] == "failed"
        assert "intentionally" in calls[3][4]

    @pytest.mark.asyncio
    async def test_no_callback_no_error(self):
        stages = [FakeStage("s1")]
        processor = JobProcessor(stages=stages, stage_callback=None)

        context = StageContext(
            job_id="test", query="q", max_shorts=5,
            aspect_ratio="9:16", crop_position="center",
            subtitle_language="pt", subtitle_style={}, settings={},
        )

        await processor.process(context)
        # No callback set → no error
