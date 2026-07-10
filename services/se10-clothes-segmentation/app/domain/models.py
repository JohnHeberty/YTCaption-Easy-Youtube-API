"""Pydantic request/response models for SE10 Clothes Segmentation."""
from __future__ import annotations

from pydantic import BaseModel, Field


class DetectedObject(BaseModel):
    """A single detected clothing item."""
    class_name: str = Field(description="Clothing class name")
    confidence: float = Field(ge=0.0, le=1.0, description="Detection confidence")
    bbox: list[int] = Field(description="[x1, y1, x2, y2] bounding box in pixels")
    area_pct: float = Field(description="Object area as percentage of image area")


class SegmentResult(BaseModel):
    """Result of a successful segmentation."""
    detected: bool = Field(description="Whether clothing was detected")
    object_count: int = Field(description="Number of detected objects")
    objects: list[DetectedObject] = Field(description="List of detected objects")
    mask_image: str | None = Field(
        default=None, description="Base64-encoded annotated image (data:image/jpeg;base64,...)"
    )
    masks: list[str] | None = Field(
        default=None, description="List of base64-encoded binary masks (data:image/png;base64,...), one per detected object"
    )
    controlnet_image: str | None = Field(
        default=None, description="Base64-encoded OpenPose-style control image (data:image/png;base64,...)"
    )
    pose_landmarks: list[dict[str, object]] | None = Field(
        default=None, description="Detected pose landmarks for debugging"
    )
    processing_time_ms: float = Field(description="Processing time in milliseconds")


class SegmentResponse(BaseModel):
    """Standard API response for segmentation."""
    success: bool = Field(description="Whether segmentation succeeded")
    message: str = Field(description="Human-readable status message")
    result: SegmentResult | None = Field(default=None, description="Segmentation result (if success)")
    error: str | None = Field(default=None, description="Error message (if failed)")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(description="Overall health status: ok, degraded, error")
    model_loaded: bool = Field(description="Whether the segmentation model is loaded")
    device: str = Field(description="Compute device: cpu, cuda, cuda:0, etc.")
    version: str = Field(description="Service version")


class DeepHealthResponse(BaseModel):
    """Detailed health check response."""
    status: str = Field(description="Overall health status")
    model_loaded: bool = Field(description="Whether the segmentation model is loaded")
    device: str = Field(description="Compute device")
    version: str = Field(description="Service version")
    checkpoints: dict[str, dict[str, object]] = Field(description="Model checkpoint status")
    uptime_s: float = Field(description="Server uptime in seconds")


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str = Field(description="Error type or code")
    message: str = Field(description="Human-readable error message")
    details: dict[str, object] | None = Field(default=None, description="Additional error details")


class PingResponse(BaseModel):
    """Liveness probe response."""
    pong: bool = Field(description="Always true when service is alive")


class DeleteJobResponse(BaseModel):
    """Job deletion response."""
    message: str = Field(description="Deletion confirmation message")
    job_id: str = Field(description="ID of deleted job")
