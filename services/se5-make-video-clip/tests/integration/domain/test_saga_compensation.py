"""Integration tests for Saga pattern (compensation) in JobProcessor."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock

from app.domain.job_processor import JobProcessor
from app.domain.job_stage import JobStage, StageContext, StageStatus


class RecordingStage(JobStage):
    """A stage that records execution and compensation calls."""

    def __init__(self, name: str) -> None:
        super().__init__(name, progress_start=0.0, progress_end=100.0)
        self.executed = False
        self.compensated = False

    def validate(self, context: StageContext) -> None:
        pass

    async def execute(self, context: StageContext) -> dict:
        self.executed = True
        return {"stage": self.name}

    async def compensate(self, context: StageContext) -> None:
        self.compensated = True


class FailingAfterStage(JobStage):
    """A stage that fails after stage 'target' has completed."""

    def __init__(self, name: str, fail_msg: str = "boom") -> None:
        super().__init__(name, progress_start=0.0, progress_end=100.0)
        self._fail_msg = fail_msg

    def validate(self, context: StageContext) -> None:
        pass

    async def execute(self, context: StageContext) -> dict:
        raise RuntimeError(self._fail_msg)


class CompensatingStage(JobStage):
    """A stage with custom compensate logic that cleans up."""

    def __init__(self, name: str, cleanup_fn=None) -> None:
        super().__init__(name, progress_start=0.0, progress_end=100.0)
        self.executed = False
        self.compensated = False
        self._cleanup_fn = cleanup_fn

    def validate(self, context: StageContext) -> None:
        pass

    async def execute(self, context: StageContext) -> dict:
        self.executed = True
        return {"stage": self.name}

    async def compensate(self, context: StageContext) -> None:
        self.compensated = True
        if self._cleanup_fn:
            self._cleanup_fn(self.name)


@pytest.mark.integration
class TestSagaCompensation:
    @pytest.mark.asyncio
    async def test_compensation_called_on_failure(self):
        """When a stage fails, previously completed stages should be compensated."""
        s1 = RecordingStage("stage_1")
        s2 = RecordingStage("stage_2")
        s3 = FailingAfterStage("stage_3")
        processor = JobProcessor(stages=[s1, s2, s3])

        ctx = StageContext(
            job_id="saga_01",
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
        assert s2.executed is True
        assert s1.compensated is True
        assert s2.compensated is True

    @pytest.mark.asyncio
    async def test_compensation_reverse_order(self):
        """Compensation should happen in reverse order of completion."""
        compensation_order = []

        def track(name):
            compensation_order.append(name)

        s1 = CompensatingStage("alpha", cleanup_fn=track)
        s2 = CompensatingStage("beta", cleanup_fn=track)
        s3 = CompensatingStage("gamma", cleanup_fn=track)
        s4 = FailingAfterStage("delta")
        processor = JobProcessor(stages=[s1, s2, s3, s4])

        ctx = StageContext(
            job_id="saga_reverse",
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

        assert compensation_order[:3] == ["gamma", "beta", "alpha"]

    @pytest.mark.asyncio
    async def test_no_compensation_when_all_succeed(self):
        """When all stages succeed, no compensation should occur."""
        s1 = RecordingStage("ok1")
        s2 = RecordingStage("ok2")
        s3 = RecordingStage("ok3")
        processor = JobProcessor(stages=[s1, s2, s3])

        ctx = StageContext(
            job_id="saga_noop",
            query="test",
            max_shorts=5,
            aspect_ratio="9:16",
            crop_position="center",
            subtitle_language="pt",
            subtitle_style={},
            settings={},
        )

        await processor.process(ctx)

        assert not s1.compensated
        assert not s2.compensated
        assert not s3.compensated

    @pytest.mark.asyncio
    async def test_compensation_failure_does_not_stop_other_compensations(self):
        """If one stage's compensate() fails, others should still be compensated."""

        class BadCompensateStage(JobStage):
            def __init__(self, name):
                super().__init__(name, progress_start=0.0, progress_end=100.0)
                self.compensated = False

            def validate(self, context):
                pass

            async def execute(self, context):
                return {}

            async def compensate(self, context):
                raise RuntimeError("compensate failed!")

        s1 = RecordingStage("good1")
        s2 = BadCompensateStage("bad_compensate")
        s3 = RecordingStage("good3")
        s4 = FailingAfterStage("trigger_fail")
        processor = JobProcessor(stages=[s1, s2, s3, s4])

        ctx = StageContext(
            job_id="saga_resilient",
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

        assert s1.compensated is True
        assert s3.compensated is True

    @pytest.mark.asyncio
    async def test_completed_stages_tracked_during_processing(self):
        """completed_stages should only contain stages that finished successfully."""
        s1 = RecordingStage("done")
        s2 = FailingAfterStage("fail")
        processor = JobProcessor(stages=[s1, s2])

        ctx = StageContext(
            job_id="saga_tracking",
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

        assert processor.get_completed_stages() == ["done"]

    @pytest.mark.asyncio
    async def test_empty_stages_compensate_noop(self):
        """Empty processor should handle compensation without errors."""
        processor = JobProcessor(stages=[])
        ctx = StageContext(
            job_id="saga_empty",
            query="test",
            max_shorts=5,
            aspect_ratio="9:16",
            crop_position="center",
            subtitle_language="pt",
            subtitle_style={},
            settings={},
        )

        await processor.process(ctx)
        assert processor.completed_stages == []

    @pytest.mark.asyncio
    async def test_stage_results_marked_compensated(self):
        """After compensation, completed stage results should have COMPENSATED status."""
        s1 = RecordingStage("s1")
        s2 = FailingAfterStage("s2")
        processor = JobProcessor(stages=[s1, s2])

        ctx = StageContext(
            job_id="saga_status",
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

        result = ctx.get_result("s1")
        assert result is not None
        assert result.status == StageStatus.COMPENSATED
