"""Image-mode processors — vary, upscale, FreeU, ControlNet.

Extracted from worker.py. All follow the same pattern:
take (async_task, pipeline, ...) -> modify pipeline state.
"""
from __future__ import annotations

import base64
import io
import os
from typing import Any

from common.log_utils import get_logger

logger = get_logger(__name__)


def apply_vary(async_task, tasks: list) -> tuple[list, dict]:
    """Apply upscale/vary mode. Returns modified tasks and state."""
    if not async_task.uov_input_image:
        return tasks, {}

    method = async_task.uov_method or "subtle_variation"
    denoising_map = {
        "subtle_variation": 0.5,
        "strong_variation": 0.85,
        "upscale_15": 0.5,
        "upscale_2": 0.5,
        "upscale_fast": 0.5,
        "upscale_custom": 0.5,
    }
    denoising = denoising_map.get(method, 0.5)
    return tasks, {"mode": "vary", "method": method, "denoising": denoising}


def apply_upscale(async_task, tasks: list) -> tuple[list, dict]:
    """Apply upscale mode. Returns modified tasks and state."""
    if async_task.uov_method not in ("upscale_15", "upscale_2", "upscale_fast", "upscale_custom"):
        return tasks, {}

    scale_map = {"upscale_15": 1.5, "upscale_2": 2.0, "upscale_fast": 1.0, "upscale_custom": 1.0}
    scale = scale_map.get(async_task.uov_method, 1.5)
    upscale_value = async_task.upscale_value if async_task.uov_method == "upscale_custom" else None

    return tasks, {
        "mode": "upscale",
        "scale": upscale_value or scale,
        "method": async_task.uov_method,
    }


def apply_freeu(async_task, pipeline: Any) -> None:
    """Apply FreeU patch if enabled."""
    if not async_task.freeu_enabled:
        return
    try:
        from app.infrastructure.operators import FreeU_V2
        if pipeline.model_base and pipeline.model_base.has_unet:
            FreeU_V2.patch(
                pipeline.model_base.unet.model,
                async_task.freeu_b1,
                async_task.freeu_b2,
                async_task.freeu_s1,
                async_task.freeu_s2,
            )
    except (RuntimeError, ValueError) as e:
        logger.warning("Failed to apply FreeU: %s", e)


def apply_controlnet(
    async_task,
    pipeline: Any,
    positive_cond: Any,
    negative_cond: Any,
    width: int,
    height: int,
) -> tuple[Any, Any]:
    """Apply ControlNet conditioning (OpenPose) to positive/negative conditioning."""
    import numpy as np
    from PIL import Image
    from app.infrastructure.core_ops import load_controlnet, apply_controlnet as _apply_cn
    from app.services import preprocessors
    from modules.config import path_controlnet

    cn_openpose = async_task.cn_tasks.get("cn_openpose", [])
    if not cn_openpose:
        return positive_cond, negative_cond

    import cv2
    import torch
    import modules.core as core

    openpose_path = os.path.join(path_controlnet, "controlnet-union-sdxl-1.0.safetensors")
    if not os.path.exists(openpose_path):
        logger.warning("OpenPose ControlNet model not found: %s", openpose_path)
        return positive_cond, negative_cond

    try:
        controlnet = load_controlnet(openpose_path)
    except (RuntimeError, OSError) as e:
        logger.warning("Failed to load OpenPose ControlNet: %s", e)
        return positive_cond, negative_cond

    def _decode_b64(img_b64: str) -> np.ndarray | None:
        try:
            if "," in img_b64:
                img_b64 = img_b64.split(",", 1)[1]
            img_bytes = base64.b64decode(img_b64)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            return np.array(img).astype(np.uint8)
        except (ValueError, OSError) as e:
            logger.warning("Failed to decode control image: %s", e)
            return None

    def _decode_bytes(img_bytes: bytes) -> np.ndarray | None:
        try:
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            return np.array(img).astype(np.uint8)
        except (ValueError, OSError) as e:
            logger.warning("Failed to decode control image bytes: %s", e)
            return None

    for cn_img_b64, cn_stop, cn_weight in cn_openpose:
        img = None
        if isinstance(cn_img_b64, str):
            img = _decode_b64(cn_img_b64)
        elif isinstance(cn_img_b64, bytes):
            img = _decode_bytes(cn_img_b64)
        elif isinstance(cn_img_b64, np.ndarray):
            img = cn_img_b64
        elif hasattr(cn_img_b64, "convert"):
            img = np.array(cn_img_b64.convert("RGB")).astype(np.uint8)
        else:
            logger.warning("OpenPose control image has unexpected type: %s", type(cn_img_b64).__name__)
            continue

        if img is None:
            continue

        logger.info("OpenPose control image | raw_shape=%s dtype=%s target=%dx%d", img.shape, img.dtype, width, height)

        # Ensure contiguous uint8 HWC array for OpenCV
        img = np.ascontiguousarray(img)
        if img.dtype != np.uint8:
            img = img.astype(np.uint8)

        # Resize to target diffusion size
        img = cv2.resize(img, (width, height), interpolation=cv2.INTER_LANCZOS4)
        img = preprocessors.openpose_identity(img)
        logger.info("OpenPose control image | resized_shape=%s", img.shape)

        # Convert to tensor [B, H, W, C] float
        img_tensor = torch.from_numpy(img.astype(np.float32) / 255.0).unsqueeze(0)

        try:
            positive_cond, negative_cond = _apply_cn(
                positive_cond, negative_cond,
                controlnet, img_tensor,
                strength=float(cn_weight),
                start_percent=0.0,
                end_percent=float(cn_stop),
            )
            logger.info("Applied OpenPose ControlNet | weight=%.2f stop=%.2f", cn_weight, cn_stop)
        except (RuntimeError, ValueError) as e:
            logger.warning("Failed to apply OpenPose ControlNet: %s", e)

    return positive_cond, negative_cond
