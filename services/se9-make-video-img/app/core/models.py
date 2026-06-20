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
    t: float
    text: str


class SceneSuggestion(BaseModel):
    t: float
    visual: str


class OnScreenText(BaseModel):
    t: float
    text: str


class CreateVideoRequest(BaseModel):
    post_id: str
    hook: str
    estimated_seconds: int
    language: str = "pt-BR"
    content_rating: str = "Geral"
    narration: list[NarrationSegment]
    scene_suggestions: list[SceneSuggestion]
    on_screen_text: list[OnScreenText] = []
    title_options: list[str] = []
    hashtags: list[str] = []
    safety_notes: list[str] = []
    voice_id: str = "builtin_feminino"
    aspect_ratio: str = "9:16"
    zoom_style: str = "random"
    webhook_url: str | None = None
    normalize_text: bool = True


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
