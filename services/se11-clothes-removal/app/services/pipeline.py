"""Pipeline for SE11 Clothes Removal — orchestrates SE10 → SE8."""
import base64
import os
import time
from typing import Optional

from common.log_utils import get_logger
from common.datetime_utils import now_brazil

from app.core.config import settings
from app.core.models import ClothesRemovalJob, ClothesRemovalJobStatus
from app.infrastructure.http_client import SE10Client, SE8Client
from app.infrastructure.redis_store import ClothesRemovalJobStore

logger = get_logger(__name__)


def _decode_image(image_input: str) -> bytes:
    """Decode base64 image or fetch from URL. Returns raw bytes."""
    if image_input.startswith(("http://", "https://")):
        import httpx
        resp = httpx.get(image_input, timeout=30)
        resp.raise_for_status()
        return resp.content

    # Strip data URI prefix if present
    if "," in image_input and image_input.startswith("data:"):
        image_input = image_input.split(",", 1)[1]

    return base64.b64decode(image_input)


def _to_data_uri(b64_str: str, mime: str = "image/png") -> str:
    """Ensure base64 string has data URI prefix."""
    if b64_str.startswith("data:"):
        return b64_str
    return f"data:{mime};base64,{b64_str}"


def _strip_data_uri(data_uri: str) -> str:
    """Strip data URI prefix, return raw base64."""
    if "," in data_uri and data_uri.startswith("data:"):
        return data_uri.split(",", 1)[1]
    return data_uri


def combine_masks(masks: list[str]) -> str:
    """Combine multiple binary masks into one using OpenCV union.

    Args:
        masks: List of base64 PNG masks (with or without data URI prefix).

    Returns:
        Combined mask as base64 data URI (data:image/png;base64,...).
    """
    import cv2
    import numpy as np

    combined = None
    for mask_b64 in masks:
        raw = _strip_data_uri(mask_b64)
        mask_bytes = base64.b64decode(raw)
        nparr = np.frombuffer(mask_bytes, np.uint8)
        mask_img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        if mask_img is None:
            continue

        if combined is None:
            combined = mask_img
        else:
            # Resize if dimensions differ
            if combined.shape != mask_img.shape:
                mask_img = cv2.resize(mask_img, (combined.shape[1], combined.shape[0]))
            # Union of masks
            combined = cv2.bitwise_or(combined, mask_img)

    if combined is None:
        raise ValueError("No valid masks to combine")

    # Ensure binary
    combined = (combined > 127).astype(np.uint8) * 255

    # Encode as PNG base64
    _, buffer = cv2.imencode(".png", combined)
    return f"data:image/png;base64,{base64.b64encode(buffer).decode('utf-8')}"


async def run_clothes_removal(job: ClothesRemovalJob, store: ClothesRemovalJobStore):
    """Main pipeline: image → SE10 (detect) → combine masks → SE8 (inpaint) → result."""
    logger.info("Starting clothes removal pipeline for job %s", job.job_id)

    se10 = SE10Client()
    se8 = SE8Client()

    try:
        # === Stage 1: Decode image ===
        image_bytes = _decode_image(job.request.image)
        logger.info("Job %s: image decoded (%d bytes)", job.job_id, len(image_bytes))

        # === Stage 2: SE10 — Detect clothing ===
        job.status = ClothesRemovalJobStatus.DETECTING
        job.update_stage("detecting", "processing", progress=10.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        t0 = time.time()
        segment_result = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}.jpg",
            classes=job.request.classes,
            box_threshold=job.request.box_threshold,
            text_threshold=job.request.text_threshold,
        )
        seg_time = time.time() - t0
        logger.info(
            "Job %s: SE10 detected %d objects in %.1fs",
            job.job_id, segment_result.get("object_count", 0), seg_time,
        )

        if not segment_result.get("detected"):
            job.status = ClothesRemovalJobStatus.COMPLETED
            job.error = "No clothing detected in image"
            job.progress = 100.0
            job.update_stage("detecting", "completed", progress=100.0)
            job.update_stage("inpainting", "completed", progress=100.0)
            store.save_job(job.job_id, job.model_dump(mode="json"))
            await se10.close()
            await se8.close()
            return

        masks = segment_result.get("masks", [])
        if not masks:
            job.status = ClothesRemovalJobStatus.FAILED
            job.error = "SE10 detected objects but returned no masks"
            job.update_stage("detecting", "failed", error="No masks returned")
            store.save_job(job.job_id, job.model_dump(mode="json"))
            await se10.close()
            await se8.close()
            return

        job.objects_detected = len(masks)
        job.update_stage("detecting", "completed", progress=100.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        # === Stage 3: Combine masks ===
        job.update_stage("inpainting", "processing", progress=10.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        combined_mask = combine_masks(masks)
        logger.info("Job %s: combined %d masks", job.job_id, len(masks))

        # === Stage 4: SE8 — Inpainting ===
        image_b64 = _to_data_uri(base64.b64encode(image_bytes).decode("utf-8"), mime="image/jpeg")

        t1 = time.time()
        inpaint_result = await se8.inpaint(
            image_b64=image_b64,
            mask_b64=combined_mask,
            prompt=job.request.prompt,
            negative_prompt=job.request.negative_prompt,
            inpaint_strength=job.request.inpaint_strength,
        )
        inpaint_time = time.time() - t1
        logger.info("Job %s: SE8 inpainting completed in %.1fs", job.job_id, inpaint_time)

        # === Stage 5: Save result ===
        result_b64 = inpaint_result.get("base64", "")
        if not result_b64:
            job.status = ClothesRemovalJobStatus.FAILED
            job.error = "SE8 returned empty result"
            job.update_stage("inpainting", "failed", error="Empty SE8 result")
            store.save_job(job.job_id, job.model_dump(mode="json"))
            await se10.close()
            await se8.close()
            return

        # Save to file
        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)
        result_path = os.path.join(output_dir, f"{job.job_id}_result.png")

        result_bytes = base64.b64decode(_strip_data_uri(result_b64))
        with open(result_path, "wb") as f:
            f.write(result_bytes)

        job.result_path = result_path
        job.status = ClothesRemovalJobStatus.COMPLETED
        job.progress = 100.0
        job.update_stage("inpainting", "completed", progress=100.0)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

        logger.info(
            "Job %s: completed — %d objects detected, result saved to %s",
            job.job_id, job.objects_detected, result_path,
        )

    except Exception as e:
        logger.error("Job %s failed: %s", job.job_id, e, exc_info=True)
        job.status = ClothesRemovalJobStatus.FAILED
        job.error = str(e)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

    finally:
        await se10.close()
        await se8.close()
