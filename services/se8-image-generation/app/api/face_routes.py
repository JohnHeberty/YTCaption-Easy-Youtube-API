"""Face restoration routes for SE8 Image Engine.

Exposes GFPGAN / CodeFormer face restoration as a standalone endpoint so
other services (e.g. SE11) can unify facial texture after compositing.
"""
from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime

import cv2
import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from app.api.image_utils import ndarray_to_base64png, read_input_image
from app.core.config import get_settings
from app.services.face_restoration import restore_face
from common.log_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/face", tags=["Face"])


class FaceRestoreRequest(BaseModel):
    """Request face restoration on an image."""

    image: str = Field(..., description="Base64 image or data URI (RGB/BGR).")
    model: str = Field(default="CodeFormer", description="Model name: CodeFormer or GFPGAN.")
    fidelity: float = Field(default=0.5, ge=0.0, le=1.0, description="CodeFormer fidelity (0-1).")
    require_base64: bool = Field(default=True, description="Return base64 string in response.")

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        allowed = {"CodeFormer", "GFPGAN"}
        if v not in allowed:
            raise ValueError(f"model must be one of {allowed}")
        return v


class FaceRestoreResponse(BaseModel):
    """Response from face restoration endpoint."""

    success: bool = True
    base64: str | None = None
    url: str | None = None
    model: str = "CodeFormer"
    faces_detected: int = 0
    message: str | None = None


def _save_output_image(img_rgb: np.ndarray, suffix: str = "face_restore") -> str:
    """Save restored image to output dir and return relative URL path."""
    settings = get_settings()
    output_dir = settings.output_dir

    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = os.path.join(output_dir, today)
    os.makedirs(out_dir, exist_ok=True)

    file_name = f"{suffix}_{uuid.uuid4().hex[:12]}.png"
    file_path = os.path.join(out_dir, file_name)

    # restore_face returns RGB; save as PNG via OpenCV (expects BGR)
    cv2.imwrite(file_path, cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))

    return f"/files/{today}/{file_name}"


@router.post("/restore", response_model=FaceRestoreResponse)
async def restore_faces(request: FaceRestoreRequest) -> FaceRestoreResponse:
    """Restore faces in an image using GFPGAN or CodeFormer."""
    try:
        img = read_input_image(request.image)
        if img is None:
            return FaceRestoreResponse(
                success=False,
                message="Failed to decode input image",
            )

        # read_input_image returns BGR (OpenCV convention); restore_face expects RGB
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        restored_rgb, faces_detected = await run_in_threadpool(
            restore_face,
            img_rgb,
            request.model,
            request.fidelity,
        )

        url = _save_output_image(restored_rgb)
        b64_str: str | None = None
        if request.require_base64:
            b64_str = ndarray_to_base64png(restored_rgb)

        return FaceRestoreResponse(
            success=True,
            base64=b64_str,
            url=url,
            model=request.model,
            faces_detected=faces_detected,
        )

    except Exception as e:
        logger.error("Face restore endpoint failed: %s", e, exc_info=True)
        return FaceRestoreResponse(
            success=False,
            message=str(e),
        )
