"""Segmentation routes for SE10 Clothes Segmentation."""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, File, Form, UploadFile

from app.state import get_segmentor
from app.core.config import get_settings
from app.core.constants import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB
from app.domain.models import SegmentResponse, SegmentResult, DetectedObject

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Segment"])
executor = ThreadPoolExecutor(max_workers=get_settings().worker_threads)


@router.post("/segment", response_model=SegmentResponse)
async def segment_clothes(
    file: UploadFile = File(..., description="Image file (JPG, JPEG, PNG)"),
    classes: str | None = Form(None, description="Comma-separated class override"),
    box_threshold: float | None = Form(None, description="Detection confidence threshold"),
    text_threshold: float | None = Form(None, description="Text matching threshold"),
    mode: str = Form("clothes", description="Detection mode: 'clothes' or 'person'"),
    detector: str = Form("segformer", description="Detector: 'segformer' (default), 'yolo11', or 'ensemble'"),
    include_pose: bool = Form(False, description="Generate OpenPose-style controlnet_image for SE8 ControlNet"),
) -> SegmentResponse:
    if not file.filename:
        return SegmentResponse(
            success=False,
            message="No filename provided",
            error="MISSING_FILENAME",
        )

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return SegmentResponse(
            success=False,
            message=f"Invalid file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            error="INVALID_FILE_TYPE",
        )

    contents = await file.read()
    if len(contents) == 0:
        return SegmentResponse(
            success=False,
            message="Empty file uploaded",
            error="EMPTY_FILE",
        )

    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        return SegmentResponse(
            success=False,
            message=f"File too large: {len(contents) / 1024 / 1024:.1f}MB (max {MAX_FILE_SIZE_MB}MB)",
            error="FILE_TOO_LARGE",
        )

    try:
        from PIL import Image
        import io
        img_test = Image.open(io.BytesIO(contents))
        img_test.verify()
    except Exception as e:
        logger.debug("Image validation failed: %s", e)
        return SegmentResponse(
            success=False,
            message="File is not a valid image (corrupt or unsupported format)",
            error="INVALID_IMAGE",
        )

    segmentor = get_segmentor()
    if segmentor is None:
        return SegmentResponse(
            success=False,
            message="Segmentation model is not loaded yet. Please try again later.",
            error="MODEL_NOT_LOADED",
        )

    class_list: list[str] | None = None
    if classes:
        class_list = [c.strip() for c in classes.split(",") if c.strip()]

    try:
        loop = asyncio.get_running_loop()
        result: dict[str, Any] = await loop.run_in_executor(
            executor,
            lambda _img=contents, _cls=class_list, _bt=box_threshold, _tt=text_threshold, _mode=mode, _det=detector, _ip=include_pose: segmentor.segment(
                image_bytes=_img,
                classes=_cls,
                box_threshold=_bt,
                text_threshold=_tt,
                mode=_mode,
                detector=_det,
                include_pose=_ip,
            ),
        )
    except Exception as e:
        logger.error("Segmentation failed: %s", e, exc_info=True)
        return SegmentResponse(
            success=False,
            message=f"Segmentation failed: {str(e)}",
            error="SEGMENTATION_ERROR",
        )

    # Unload GPU models after detection to free VRAM for SE8
    # Keep SegFormer loaded to avoid reload penalty
    try:
        segmentor.unload_gpu_models()
    except Exception as e:
        logger.debug("Failed to unload GPU models: %s", e)

    if not result["detected"]:
        label = "persons" if mode == "person" else "clothing items"
        return SegmentResponse(
            success=True,
            message=f"No {label} detected",
            result=SegmentResult(
                detected=False,
                object_count=0,
                objects=[],
                mask_image=None,
                controlnet_image=result.get("controlnet_image"),
                pose_landmarks=result.get("pose_landmarks"),
                processing_time_ms=result["processing_time_ms"],
            ),
        )

    objects = [DetectedObject(**obj) for obj in result["objects"]]
    label = "persons" if mode == "person" else "clothing items"
    return SegmentResponse(
        success=True,
        message=f"Detected {len(objects)} {label}",
        result=SegmentResult(
            detected=True,
            object_count=len(objects),
            objects=objects,
            mask_image=result.get("mask_image"),
            masks=result.get("masks"),
            controlnet_image=result.get("controlnet_image"),
            pose_landmarks=result.get("pose_landmarks"),
            processing_time_ms=result["processing_time_ms"],
        ),
    )
