"""Unit tests for the video pipeline orchestrator."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.models import (
    CreateVideoRequest,
    NarrationSegment,
    SceneSuggestion,
    StageInfo,
    StageStatus,
    VideoJob,
    VideoJobStatus,
)
from app.services.pipeline import MAX_AUDIO_RETRIES, VideoPipeline


def _make_request(**overrides) -> CreateVideoRequest:
    defaults = dict(
        post_id="post_1",
        hook="Hook text",
        estimated_seconds=30,
        narration=[NarrationSegment(t=0.0, text="Olá mundo")],
        scene_suggestions=[SceneSuggestion(t=0.0, visual="A sunset")],
    )
    defaults.update(overrides)
    return CreateVideoRequest(**defaults)


def _make_job(**overrides) -> VideoJob:
    request = overrides.pop("request", _make_request())
    defaults = dict(job_id="rbg_test123", post_id="post_1", request=request)
    defaults.update(overrides)
    return VideoJob(**defaults)


def _make_mock_store():
    store = MagicMock()
    store.save_job = MagicMock()
    return store


def _mock_audio_generator(audio_path="/tmp/audio.wav", duration=10.0):
    gen = AsyncMock()
    gen.generate = AsyncMock(return_value=(audio_path, duration))
    gen.close = AsyncMock()
    return gen


def _mock_image_generator(paths=None):
    gen = AsyncMock()
    gen.generate_all = AsyncMock(return_value=paths or ["/tmp/scene_0.png"])
    gen.close = AsyncMock()
    return gen


def _mock_assembler(video_path="/tmp/video.mp4"):
    asm = AsyncMock()
    asm.assemble = AsyncMock(return_value=video_path)
    return asm


# ---------------------------------------------------------------------------
# _update_stage tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_stage_start():
    store = _make_mock_store()
    pipeline = VideoPipeline(store=store)
    job = _make_job()

    await pipeline._update_stage(job, "generating_audio", "start")

    stage = job.stages["generating_audio"]
    assert stage.status == StageStatus.PROCESSING
    assert stage.started_at is not None
    assert job.status == VideoJobStatus.GENERATING_AUDIO


@pytest.mark.asyncio
async def test_update_stage_complete():
    store = _make_mock_store()
    pipeline = VideoPipeline(store=store)
    job = _make_job()

    await pipeline._update_stage(job, "generating_audio", "start")
    await pipeline._update_stage(job, "generating_audio", "complete")

    stage = job.stages["generating_audio"]
    assert stage.status == StageStatus.COMPLETED
    assert stage.progress == 100.0
    assert stage.completed_at is not None


@pytest.mark.asyncio
async def test_update_stage_dict_deserialization():
    store = _make_mock_store()
    pipeline = VideoPipeline(store=store)
    job = _make_job()
    job.stages["generating_audio"] = {"status": "pending", "progress": 0}

    await pipeline._update_stage(job, "generating_audio", "start")

    assert isinstance(job.stages["generating_audio"], StageInfo)
    assert job.stages["generating_audio"].status == StageStatus.PROCESSING


# ---------------------------------------------------------------------------
# Full pipeline — success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_run_success():
    store = _make_mock_store()

    audio_gen = _mock_audio_generator()
    img_gen = _mock_image_generator(["/tmp/scene_0.png"])
    assembler = _mock_assembler("/tmp/video.mp4")

    pipeline = VideoPipeline(
        store=store,
        audio_generator_cls=lambda: audio_gen,
        image_generator_cls=lambda: img_gen,
        assembler_cls=lambda: assembler,
    )

    job = _make_job()

    with patch("app.services.pipeline.os.makedirs"):
        with patch("app.services.pipeline.settings") as mock_settings:
            mock_settings.output_dir = "/tmp"
            mock_settings.default_width = 1080
            mock_settings.default_height = 1920
            mock_settings.default_fps = 30
            mock_settings.default_crossfade_duration = 0.3
            mock_settings.default_image_steps = 30
            mock_settings.default_image_performance = "Quality"
            await pipeline.run(job)

    assert job.status == VideoJobStatus.COMPLETED
    assert job.progress == 100.0
    assert job.video_path == "/tmp/video.mp4"
    assert store.save_job.called


# ---------------------------------------------------------------------------
# Full pipeline — failures
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_run_audio_failure():
    store = _make_mock_store()

    failing_gen = AsyncMock()
    failing_gen.generate = AsyncMock(side_effect=Exception("SE7 down"))
    failing_gen.close = AsyncMock()

    pipeline = VideoPipeline(
        store=store,
        audio_generator_cls=lambda: failing_gen,
        image_generator_cls=lambda: _mock_image_generator(),
        assembler_cls=lambda: _mock_assembler(),
    )

    job = _make_job()

    with patch("app.services.pipeline.os.makedirs"):
        with patch("app.services.pipeline.settings") as mock_settings:
            mock_settings.output_dir = "/tmp"
            mock_settings.default_normalize_text = False
            with pytest.raises(Exception, match="SE7 down"):
                await pipeline.run(job)

    assert job.status == VideoJobStatus.FAILED
    assert "SE7 down" in (job.error or "")


@pytest.mark.asyncio
async def test_run_image_failure():
    store = _make_mock_store()

    failing_img = AsyncMock()
    failing_img.generate_all = AsyncMock(side_effect=Exception("SE8 down"))
    failing_img.close = AsyncMock()

    pipeline = VideoPipeline(
        store=store,
        audio_generator_cls=lambda: _mock_audio_generator(),
        image_generator_cls=lambda: failing_img,
        assembler_cls=lambda: _mock_assembler(),
    )

    job = _make_job()

    with patch("app.services.pipeline.os.makedirs"):
        with patch("app.services.pipeline.settings") as mock_settings:
            mock_settings.output_dir = "/tmp"
            mock_settings.default_image_steps = 30
            mock_settings.default_image_performance = "Quality"
            with pytest.raises(Exception, match="SE8 down"):
                await pipeline.run(job)

    assert job.status == VideoJobStatus.FAILED


@pytest.mark.asyncio
async def test_run_assembly_failure():
    store = _make_mock_store()

    failing_asm = AsyncMock()
    failing_asm.assemble = AsyncMock(side_effect=Exception("FFmpeg crashed"))

    pipeline = VideoPipeline(
        store=store,
        audio_generator_cls=lambda: _mock_audio_generator(),
        image_generator_cls=lambda: _mock_image_generator(),
        assembler_cls=lambda: failing_asm,
    )

    job = _make_job()

    with patch("app.services.pipeline.os.makedirs"):
        with patch("app.services.pipeline.settings") as mock_settings:
            mock_settings.output_dir = "/tmp"
            mock_settings.default_width = 1080
            mock_settings.default_height = 1920
            mock_settings.default_fps = 30
            mock_settings.default_crossfade_duration = 0.3
            with pytest.raises(Exception, match="FFmpeg crashed"):
                await pipeline.run(job)

    assert job.status == VideoJobStatus.FAILED


# ---------------------------------------------------------------------------
# Audio retry logic
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generate_audio_retry_success():
    store = _make_mock_store()
    call_count = 0

    class FlakyAudioGen:
        def __init__(self):
            pass

        async def generate(self, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return ("/tmp/audio.wav", 10.0)

        async def close(self):
            pass

    pipeline = VideoPipeline(
        store=store,
        audio_generator_cls=FlakyAudioGen,
    )
    job = _make_job()

    with patch("app.services.pipeline.asyncio.sleep", new_callable=AsyncMock):
        with patch("app.services.pipeline.settings") as mock_settings:
            mock_settings.default_normalize_text = False
            audio_path, duration = await pipeline._generate_audio(job, "/tmp")

    assert audio_path == "/tmp/audio.wav"
    assert call_count == 3


@pytest.mark.asyncio
async def test_generate_audio_all_retries_exhausted():
    store = _make_mock_store()

    class AlwaysFailAudioGen:
        def __init__(self):
            pass

        async def generate(self, **kwargs):
            raise ConnectionError("SE7 unreachable")

        async def close(self):
            pass

    pipeline = VideoPipeline(
        store=store,
        audio_generator_cls=AlwaysFailAudioGen,
    )
    job = _make_job()

    with patch("app.services.pipeline.asyncio.sleep", new_callable=AsyncMock):
        with patch("app.services.pipeline.settings") as mock_settings:
            mock_settings.default_normalize_text = False
            with pytest.raises(ConnectionError, match="SE7 unreachable"):
                await pipeline._generate_audio(job, "/tmp")


# ---------------------------------------------------------------------------
# Webhook notification
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_notify_webhook_called():
    store = _make_mock_store()
    pipeline = VideoPipeline(store=store)
    request = _make_request(webhook_url="https://example.com/hook")
    job = _make_job(request=request)

    with patch("app.api.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
        await pipeline._notify_webhook(job)
        mock_send.assert_called_once_with(job)


@pytest.mark.asyncio
async def test_notify_webhook_skipped():
    store = _make_mock_store()
    pipeline = VideoPipeline(store=store)
    request = _make_request(webhook_url=None)
    job = _make_job(request=request)

    with patch("app.api.webhook.send_webhook", new_callable=AsyncMock) as mock_send:
        await pipeline._notify_webhook(job)
        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Init defaults
# ---------------------------------------------------------------------------
def test_init_defaults():
    pipeline = VideoPipeline()
    from app.services.audio_generator import AudioGenerator
    from app.services.image_generator import ImageGenerator
    from app.services.video_assembler import VideoAssembler

    assert pipeline._audio_generator_cls is AudioGenerator
    assert pipeline._image_generator_cls is ImageGenerator
    assert pipeline._assembler_cls is VideoAssembler
