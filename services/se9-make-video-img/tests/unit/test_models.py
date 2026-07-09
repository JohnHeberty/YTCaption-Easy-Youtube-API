"""Unit tests for SE9 video generation models."""
import pytest
from app.core.models import (
    CreateVideoRequest,
    NarrationSegment,
    SceneSuggestion,
    OnScreenText,
    VideoJob,
    VideoJobStatus,
)
from app.core.constants import JOB_ID_PREFIX, ASPECT_RATIOS, ZOOM_STYLES


def test_narration_segment():
    seg = NarrationSegment(t=0, text="Hello world")
    assert seg.t == 0
    assert seg.text == "Hello world"


def test_scene_suggestion():
    scene = SceneSuggestion(t=5, visual="A sunset over mountains")
    assert scene.t == 5
    assert "sunset" in scene.visual


def test_on_screen_text():
    text = OnScreenText(t=10, text="Breaking news!")
    assert text.t == 10


def test_create_video_request():
    req = CreateVideoRequest(
        post_id="test123",
        hook="Test hook",
        estimated_seconds=60,
        narration=[NarrationSegment(t=0, text="Hello")],
        scene_suggestions=[SceneSuggestion(t=0, visual="Test scene")],
    )
    assert req.post_id == "test123"
    assert req.language == "pt-BR"
    assert req.voice_id == "builtin_feminino"
    assert req.aspect_ratio == "9:16"
    assert req.zoom_style == "random"
    assert req.webhook_url is None


def test_create_video_request_optional_fields():
    req = CreateVideoRequest(
        post_id="test",
        hook="hook",
        estimated_seconds=30,
        narration=[NarrationSegment(t=0, text="Hi")],
        scene_suggestions=[SceneSuggestion(t=0, visual="Scene")],
        on_screen_text=[OnScreenText(t=0, text="Text")],
        title_options=["Title 1", "Title 2"],
        hashtags=["#test", "#video"],
        webhook_url="https://example.com/webhook",
    )
    assert len(req.on_screen_text) == 1
    assert len(req.title_options) == 2
    assert req.webhook_url == "https://example.com/webhook"


def test_video_job_creation():
    req = CreateVideoRequest(
        post_id="test",
        hook="hook",
        estimated_seconds=30,
        narration=[NarrationSegment(t=0, text="Hi")],
        scene_suggestions=[SceneSuggestion(t=0, visual="Scene")],
    )
    job = VideoJob(
        job_id="rbg_test123",
        post_id="test",
        request=req,
    )
    assert job.job_id.startswith(JOB_ID_PREFIX)
    assert job.status == VideoJobStatus.QUEUED
    assert job.progress == 0.0
    assert "generating_audio" in job.stages
    assert "generating_images" in job.stages
    assert "assembling_video" in job.stages


def test_video_job_status_transitions():
    req = CreateVideoRequest(
        post_id="test",
        hook="hook",
        estimated_seconds=30,
        narration=[NarrationSegment(t=0, text="Hi")],
        scene_suggestions=[SceneSuggestion(t=0, visual="Scene")],
    )
    job = VideoJob(
        job_id="rbg_test",
        post_id="test",
        request=req,
    )
    job.status = VideoJobStatus.GENERATING_AUDIO
    assert job.status.value == "generating_audio"

    job.status = VideoJobStatus.GENERATING_IMAGES
    assert job.status.value == "generating_images"

    job.status = VideoJobStatus.ASSEMBLING_VIDEO
    assert job.status.value == "assembling_video"

    job.status = VideoJobStatus.COMPLETED
    assert job.status.value == "completed"


def test_aspect_ratios():
    assert "9:16" in ASPECT_RATIOS
    assert "16:9" in ASPECT_RATIOS
    assert "1:1" in ASPECT_RATIOS
    assert ASPECT_RATIOS["9:16"]["width"] == 1080
    assert ASPECT_RATIOS["9:16"]["height"] == 1920


def test_zoom_styles():
    assert len(ZOOM_STYLES) == 4
    assert "random" in ZOOM_STYLES
    assert "zoom_in" in ZOOM_STYLES
    assert "zoom_out" in ZOOM_STYLES
    assert "static" in ZOOM_STYLES


def test_job_id_prefix():
    assert JOB_ID_PREFIX == "rbg_"
