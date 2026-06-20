"""Pydantic models for SE11 Clothes Removal."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from common.datetime_utils import now_brazil


# =============================================================================
# Enums
# =============================================================================

class ClothesRemovalJobStatus(str, Enum):
    QUEUED = "queued"
    DETECTING = "detecting"
    INPAINTING = "inpainting"
    COMPLETED = "completed"
    FAILED = "failed"


class StageStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Stage tracking
# =============================================================================

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


# =============================================================================
# Request / Response
# =============================================================================

class CreateClothesRemovalRequest(BaseModel):
    """Request to create a clothes removal job."""
    image: str = Field(description="Image as base64 string or HTTP URL")
    classes: str | None = Field(
        default=None,
        description="Comma-separated clothing classes to detect (e.g. 'shirt,pants,dress'). None = all clothing.",
    )
    prompt: str = Field(default="nude, naked body, smooth skin", description="Inpainting prompt")
    negative_prompt: str = Field(default="clothes, clothing, fabric, wrinkles, folds", description="Negative prompt")
    box_threshold: float = Field(default=0.10, ge=0.0, le=1.0, description="SE10 detection threshold")
    text_threshold: float = Field(default=0.10, ge=0.0, le=1.0, description="SE10 text matching threshold")
    inpaint_strength: float = Field(default=1.0, ge=0.0, le=1.0, description="SE8 inpaint strength")
    webhook_url: str | None = Field(default=None, description="Webhook URL for completion notification")


class CreateClothesRemovalResponse(BaseModel):
    """Response when a job is created."""
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Job status for polling."""
    job_id: str
    status: str
    progress: float
    stages: dict[str, Any]
    objects_detected: int | None = None
    created_at: str
    error: str | None = None


# =============================================================================
# Job model
# =============================================================================

class ClothesRemovalJob(BaseModel):
    """Internal job representation."""
    job_id: str
    status: ClothesRemovalJobStatus = ClothesRemovalJobStatus.QUEUED
    progress: float = 0.0
    stages: dict[str, Any] = {
        "detecting": StageInfo().model_dump(),
        "inpainting": StageInfo().model_dump(),
    }
    request: CreateClothesRemovalRequest
    result_path: str | None = None
    objects_detected: int | None = None
    created_at: datetime = Field(default_factory=now_brazil)
    updated_at: datetime = Field(default_factory=now_brazil)
    error: str | None = None

    def update_progress(self) -> None:
        stage_progress = {
            "detecting": (0, 40),
            "inpainting": (40, 100),
        }
        total = 0.0
        for stage_name, (start, end) in stage_progress.items():
            stage = self.stages.get(stage_name)
            if stage:
                stage_status = stage.get("status", "pending")
                stage_prog = stage.get("progress", 0.0)
                if stage_status == "completed":
                    total += (end - start) * 1.0
                elif stage_status == "processing":
                    total += (end - start) * (stage_prog / 100.0)
        self.progress = round(total, 1)
        self.updated_at = now_brazil()

    def update_stage(self, stage_name: str, status: str, progress: float = 0.0, error: str | None = None) -> None:
        if stage_name in self.stages:
            stage = StageInfo(**self.stages[stage_name])
            if status == "processing":
                stage.start()
                stage.progress = progress
            elif status == "completed":
                stage.complete()
            elif status == "failed":
                stage.fail(error or "Unknown error")
            self.stages[stage_name] = stage.model_dump()
        self.update_progress()
