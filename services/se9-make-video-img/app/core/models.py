"""Pydantic models for the Make Video IMG service."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from common.datetime_utils import now_brazil


class VideoJobStatus(str, Enum):
    QUEUED = "queued"
    GENERATING_AUDIO = "generating_audio"
    GENERATING_IMAGES = "generating_images"
    ASSEMBLING_VIDEO = "assembling_video"
    COMPLETED = "completed"
    FAILED = "failed"


class StageStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class StageInfo(BaseModel):
    status: StageStatus = StageStatus.PENDING
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def start(self) -> None:
        self.status = StageStatus.PROCESSING
        self.started_at = now_brazil()

    def complete(self) -> None:
        self.status = StageStatus.COMPLETED
        self.completed_at = now_brazil()
        self.progress = 100.0

    def fail(self, error: str) -> None:
        self.status = StageStatus.FAILED
        self.completed_at = now_brazil()
        self.error = error


class NarrationSegment(BaseModel):
    t: float = Field(..., description="Start time in seconds from video beginning.")
    text: str = Field(..., max_length=5000, description="Narration text for this segment.")


class SceneSuggestion(BaseModel):
    t: float = Field(..., description="Start time in seconds.")
    visual: str = Field(..., max_length=2000, description="Image generation prompt for SE8 Fooocus.")
    negative_prompt: str | None = Field(default=None, max_length=2000, description="Negative prompt — what to avoid in the image.")
    camera_movement: str | None = Field(default=None, description="Camera movement: static, slow_push_in, slow_pull_out, random.")
    transition: str | None = Field(default=None, description="FFmpeg xfade transition after this scene (e.g. dissolve, fadeblack).")


class OnScreenText(BaseModel):
    t: float = Field(..., description="Start time in seconds when the caption appears.")
    text: str = Field(..., max_length=500, description="Caption text to display on screen.")
    end_seconds: float | None = Field(default=None, description="End time in seconds when the caption disappears.")


class CreateVideoRequest(BaseModel):
    post_id: str = Field(..., min_length=1, max_length=100, description="Unique post identifier from the upstream system.")
    hook: str = Field(..., max_length=500, description="Title/hook text for the video.")
    estimated_seconds: int = Field(..., ge=5, le=600, description="Target video duration in seconds.")
    language: str = Field(default="pt-BR", max_length=10, description="Language code for TTS and caption rendering.")
    content_rating: str = Field(default="Geral", max_length=20, description="Content rating hint (metadata only).")
    narration: list[NarrationSegment] = Field(..., min_length=1, description="Narration segments with timestamps.")
    scene_suggestions: list[SceneSuggestion] = Field(..., min_length=1, max_length=20, description="Visual prompts for scene images.")
    on_screen_text: list[OnScreenText] = Field(default_factory=list, description="Caption overlays with timing.")
    title_options: list[str] = Field(default_factory=list, description="Alternative title options (metadata).")
    hashtags: list[str] = Field(default_factory=list, description="Hashtags for the video (metadata).")
    safety_notes: list[str] = Field(default_factory=list, description="Safety/content notes (metadata only).")
    voice_id: str = Field(default="builtin_feminino", max_length=100, description="TTS voice identifier.")
    aspect_ratio: str = Field(default="9:16", description="Video aspect ratio: 9:16, 16:9, 1:1.")
    zoom_style: str = Field(default="random", description="Default Ken Burns zoom direction.")
    webhook_url: str | None = Field(default=None, description="Webhook URL for job completion notification.")
    normalize_text: bool = Field(default=True, description="Normalize text before TTS.")
    global_style: dict | None = Field(default=None, description="Global style constraints from upstream JSON (metadata).")


class VideoJob(BaseModel):
    job_id: str
    post_id: str
    status: VideoJobStatus = VideoJobStatus.QUEUED
    progress: float = 0.0
    stages: dict[str, StageInfo] = {
        "generating_audio": StageInfo(),
        "generating_images": StageInfo(),
        "assembling_video": StageInfo(),
    }
    request: CreateVideoRequest
    audio_path: str | None = None
    video_path: str | None = None
    images: list[str] = []
    created_at: datetime = Field(default_factory=now_brazil)
    updated_at: datetime = Field(default_factory=now_brazil)
    error: str | None = None

    def update_progress(self) -> None:
        stage_progress = {
            "generating_audio": (0, 40),
            "generating_images": (40, 70),
            "assembling_video": (70, 100),
        }
        total = 0.0
        for stage_name, (start, end) in stage_progress.items():
            stage = self.stages.get(stage_name)
            if stage:
                total += (end - start) * (stage.progress / 100.0)
        self.progress = round(total, 1)
        self.updated_at = now_brazil()


class CreateVideoResponse(BaseModel):
    job_id: str
    status: str
    post_id: str
    estimated_seconds: int
    scenes_count: int
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    stages: dict[str, dict[str, object]]
    created_at: str
    error: str | None = None


class WebhookPayload(BaseModel):
    event: str = "video_ready"
    job_id: str
    post_id: str
    status: str
    download_url: str
    title: str | None = None
    hashtags: list[str] = []
    duration_seconds: int | None = None
    file_size_mb: float | None = None
