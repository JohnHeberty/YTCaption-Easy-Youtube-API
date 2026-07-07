"""Domain models for SE11 Clothes Removal.

Internal job representation — NOT used for API serialization.
API schemas are in app/api/schemas.py.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, ConfigDict

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


class RemovalMode(str, Enum):
    CLOTHES = "clothes"
    PERSON = "person"
    NSFW = "nsfw"
    NSFW_TEST = "nsfw_test"


class DetectorType(str, Enum):
    GROUNDINGDINO = "groundingdino"
    SEGFORMER = "segformer"
    ENSEMBLE = "ensemble"


# =============================================================================
# Stage tracking
# =============================================================================

class StageInfo(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

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


def _default_stages() -> dict[str, Any]:
    """Factory function for mutable default stages dict."""
    return {
        "detecting": StageInfo().model_dump(),
        "inpainting": StageInfo().model_dump(),
    }


# =============================================================================
# Request (lightweight — for internal use by pipelines)
# =============================================================================

class CreateClothesRemovalRequest(BaseModel):
    """Internal request model — mirrors API schema but without OpenAPI metadata."""
    model_config = ConfigDict(str_strip_whitespace=True)

    image: str
    mode: str = "clothes"
    classes: str | None = None
    prompt: str = ""
    negative_prompt: str = ""
    box_threshold: float = 0.10
    text_threshold: float = 0.10
    inpaint_strength: float = 1.0
    per_garment: bool = False
    webhook_url: str | None = None
    detector: str = "groundingdino"
    face_blend_mode: Literal["alpha", "laplacian"] = "laplacian"
    face_restore: bool = False
    face_restore_model: Literal["CodeFormer", "GFPGAN"] = "CodeFormer"
    face_restore_fidelity: float = 0.5
    inpaint_mode: str = "invert_mask"
    use_faceid: bool = True
    faceid_weight: float = 0.8
    test_inpaint_strength: float = 0.35
    base_model: str = "lustifySDXLNSFW_v20-inpainting.safetensors"


# =============================================================================
# Job model
# =============================================================================

class ClothesRemovalJob(BaseModel):
    """Internal job representation."""
    model_config = ConfigDict(validate_assignment=True)

    job_id: str
    status: ClothesRemovalJobStatus = ClothesRemovalJobStatus.QUEUED
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    stages: dict[str, Any] = Field(default_factory=_default_stages)
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
