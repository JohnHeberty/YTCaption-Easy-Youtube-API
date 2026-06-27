"""API schemas for SE11 Clothes Removal — request/response models.

Separated from domain models for clean architecture.
All schemas use FlexibleSchema (extra="allow") for forward compatibility.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class FlexibleSchema(BaseModel):
    model_config = {"extra": "allow"}


# =============================================================================
# Request
# =============================================================================

class CreateClothesRemovalRequest(BaseModel):
    """Request to create a clothes removal job."""

    model_config = {"str_strip_whitespace": True, "validate_assignment": True}

    image: str = Field(
        ...,
        description="Image as base64-encoded string, data URI, or HTTP(S) URL",
        examples=["data:image/png;base64,iVBOR...", "https://example.com/photo.jpg"],
    )
    mode: Literal["clothes", "person", "nsfw", "nsfw_test"] = Field(
        default="clothes",
        description=(
            "Processing mode: "
            "'clothes' — default clothing removal; "
            "'person' — full torso removal; "
            "'nsfw' — production NSFW pipeline (body_mask + retry + pose validation); "
            "'nsfw_test' — alias for nsfw"
        ),
        examples=["clothes"],
    )
    classes: str | None = Field(
        default=None,
        description="Comma-separated clothing classes to detect (e.g. 'shirt,pants,dress'). None = auto-detect all clothing.",
        examples=["spaghetti strap, camisole, top, blouse"],
    )
    prompt: str = Field(
        default="",
        max_length=2000,
        description="Inpainting prompt (what to generate in masked area). Empty = default.",
        examples=["bare skin, realistic skin texture, photorealistic"],
    )
    negative_prompt: str = Field(
        default="",
        max_length=2000,
        description="Negative prompt (what to avoid). Empty = default.",
        examples=["deformed, blurry, cartoon"],
    )
    box_threshold: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="SE10 detection confidence threshold",
        examples=[0.10],
    )
    text_threshold: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="SE10 text matching threshold (Florence-2)",
        examples=[0.10],
    )
    inpaint_strength: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="SE8 inpaint denoise strength (0=preserve, 1=full generation)",
        examples=[1.0],
    )
    per_garment: bool = Field(
        default=False,
        description="Inpaint each garment separately (slower but better quality)",
    )
    webhook_url: str | None = Field(
        default=None,
        description="Webhook URL for job completion notification (POST with job status)",
        examples=["https://example.com/webhook"],
    )
    detector: Literal["groundingdino", "florence2"] = Field(
        default="groundingdino",
        description="Object detection engine: 'groundingdino' (default) or 'florence2'",
        examples=["groundingdino"],
    )


# =============================================================================
# Response — Jobs
# =============================================================================

class CreateClothesRemovalResponse(FlexibleSchema):
    """Response when a clothes removal job is created."""
    job_id: str = Field(..., description="Unique job identifier", examples=["cr_a1b2c3d4e5f6"])
    status: str = Field(default="queued", description="Initial job status", examples=["queued"])
    message: str = Field(default="Job created successfully", description="Human-readable status message")


class JobStageInfo(FlexibleSchema):
    """Stage progress information."""
    status: str = Field(default="pending", description="Stage status: pending|processing|completed|failed")
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="Stage progress percentage")
    error: str | None = Field(default=None, description="Error message if stage failed")
    started_at: str | None = Field(default=None, description="ISO timestamp when stage started")
    completed_at: str | None = Field(default=None, description="ISO timestamp when stage completed")


class JobStatusResponse(FlexibleSchema):
    """Full job status for polling."""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status: queued|detecting|inpainting|completed|failed")
    progress: float = Field(..., ge=0.0, le=100.0, description="Overall progress percentage")
    stages: dict[str, Any] = Field(default_factory=dict, description="Stage details (detecting, inpainting)")
    objects_detected: int | None = Field(default=None, description="Number of clothing objects detected")
    created_at: str = Field(..., description="Job creation timestamp (ISO 8601)")
    error: str | None = Field(default=None, description="Error message if job failed")
    result_path: str | None = Field(default=None, description="Path to result image (internal)")


class JobListItem(FlexibleSchema):
    """Lightweight job info for list views."""
    job_id: str
    status: str
    progress: float = 0.0
    objects_detected: int | None = None
    created_at: str | None = None


class ListJobsResponse(FlexibleSchema):
    """Paginated job list."""
    jobs: list[JobListItem] = Field(default_factory=list)
    total: int = Field(default=0, description="Total number of jobs")


# =============================================================================
# Response — Delete
# =============================================================================

class DeleteJobResponse(FlexibleSchema):
    """Response when a job is deleted."""
    message: str
    job_id: str


# =============================================================================
# Response — Health
# =============================================================================

class HealthResponse(FlexibleSchema):
    """Basic health check response."""
    status: str
    service: str = "clothes-removal"
    version: str = "1.0.0"


class DeepHealthCheck(FlexibleSchema):
    """Individual service health status."""
    status: str = Field(..., description="ok|unreachable|unknown")
    latency_ms: float | None = None


class DeepHealthResponse(FlexibleSchema):
    """Deep health check with upstream services."""
    status: str
    service: str = "clothes-removal"
    version: str = "1.0.0"
    checks: dict[str, Any] = Field(default_factory=dict)


class PingResponse(FlexibleSchema):
    """Simple ping response."""
    pong: bool = True


# =============================================================================
# Response — Admin
# =============================================================================

class AdminStatsResponse(FlexibleSchema):
    """System statistics."""
    jobs: dict[str, Any] = Field(default_factory=dict, description="Job counts by status")
    storage: dict[str, Any] = Field(default_factory=dict, description="Disk usage info")


class AdminCleanupResponse(FlexibleSchema):
    """Cleanup result."""
    cleaned: int = Field(default=0, description="Number of jobs cleaned up")


# =============================================================================
# Response — Errors
# =============================================================================

class ErrorResponse(FlexibleSchema):
    """Standard error response."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(default=None, description="Additional error details")
