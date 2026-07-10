"""Domain models for the Make Video IMG service.

Domain-specific types with business logic (VideoJob, StageInfo, WebhookPayload).
API-facing types (enums, request/response) live in app.api.schemas.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from common.datetime_utils import now_brazil

# Re-export API types for backward compatibility
from app.api.schemas import (  # noqa: F401
    VideoJobStatus,
    StageStatus,
    NarrationSegment,
    SceneSuggestion,
    OnScreenText,
    SFxCue,
    SilenceCue,
    CreateVideoRequest,
)


class StageInfo(BaseModel):
    """Pipeline stage progress tracker with domain methods."""
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


class VideoJob(BaseModel):
    """Domain model for a video generation job."""
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


class WebhookPayload(BaseModel):
    """Domain model for webhook notification."""
    event: str = "video_ready"
    job_id: str
    post_id: str
    status: str
    download_url: str
    title: str | None = None
    hashtags: list[str] = []
    duration_seconds: int | None = None
    file_size_mb: float | None = None
