from pydantic import BaseModel, Field
from typing import List, Optional


class DetectedObject(BaseModel):
    class_name: str
    confidence: float
    bbox: List[int] = Field(description="[x1, y1, x2, y2]")


class SegmentResponse(BaseModel):
    detected: bool
    objects: List[DetectedObject]
    mask_image: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
