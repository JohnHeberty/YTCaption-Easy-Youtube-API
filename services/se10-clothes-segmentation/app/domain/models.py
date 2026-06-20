"""Pydantic request/response models for SE10 Clothes Segmentation."""

from typing import List, Optional

from pydantic import BaseModel, Field


class DetectedObject(BaseModel):
    """A single detected clothing item."""
    class_name: str = Field(description="Clothing class name")
    confidence: float = Field(ge=0.0, le=1.0, description="Detection confidence")
    bbox: List[int] = Field(description="[x1, y1, x2, y2] bounding box in pixels")
    area_pct: float = Field(description="Object area as percentage of image area")


class SegmentResult(BaseModel):
    """Result of a successful segmentation."""
    detected: bool
    object_count: int
    objects: List[DetectedObject]
    mask_image: Optional[str] = Field(
        default=None, description="Base64-encoded annotated image (data:image/jpeg;base64,...)"
    )
    masks: Optional[List[str]] = Field(
        default=None, description="List of base64-encoded binary masks (data:image/png;base64,...), one per detected object"
    )
    processing_time_ms: float


class SegmentResponse(BaseModel):
    """Standard API response for segmentation."""
    success: bool
    message: str
    result: Optional[SegmentResult] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool
    device: str
    version: str


class DeepHealthResponse(BaseModel):
    """Detailed health check response."""
    status: str
    model_loaded: bool
    device: str
    version: str
    checkpoints: dict
    uptime_s: float


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    details: Optional[dict] = None
