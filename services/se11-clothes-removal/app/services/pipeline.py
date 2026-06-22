"""Pipeline for SE11 Clothes Removal — orchestrates SE10 → SE8 → post-process."""
from __future__ import annotations

import base64
import io
import os
import time

from common.log_utils import get_logger
from common.datetime_utils import now_brazil

from app.core.config import settings
from app.core.models import ClothesRemovalJob, ClothesRemovalJobStatus
from app.infrastructure.http_client import SE10Client, SE8Client
from app.infrastructure.redis_store import ClothesRemovalJobStore

logger = get_logger(__name__)

BEST_CLOTHING_CLASSES = "top, blouse, camisole, shirt, spaghetti strap"

DEFAULT_CLOTHES_PROMPT = (
    "natural skin tone matching surrounding skin, seamless texture, "
    "photorealistic, professional photography, soft lighting"
)
DEFAULT_CLOTHES_NEGATIVE = (
    "clothes, fabric, bra, straps, underwear, text, watermark, "
    "deformed, blurry, cartoon, anime, painting, CGI, 3d render, "
    "nipples, areola, breast, nudity, nude, naked, "
    "color mismatch, visible seams, collage, "
    "bad anatomy, deformed skin, wrinkled, scarred"
)


def _decode_image(image_input: str) -> bytes:
    if image_input.startswith(("http://", "https://")):
        import httpx
        resp = httpx.get(image_input, timeout=30)
        resp.raise_for_status()
        return resp.content
    if "," in image_input and image_input.startswith("data:"):
        image_input = image_input.split(",", 1)[1]
    return base64.b64decode(_fix_b64_padding(image_input))


def _to_data_uri(b64_str: str, mime: str = "image/png") -> str:
    if b64_str.startswith("data:"):
        return b64_str
    return f"data:{mime};base64,{b64_str}"


def _strip_data_uri(data_uri: str) -> str:
    if "," in data_uri and data_uri.startswith("data:"):
        return data_uri.split(",", 1)[1]
    return data_uri


def _fix_b64_padding(s: str) -> str:
    missing = len(s) % 4
    if missing:
        s += "=" * (4 - missing)
    return s


def combine_masks(masks: list[str]) -> str:
    import cv2
    import numpy as np

    combined = None
    for mask_b64 in masks:
        raw = _strip_data_uri(mask_b64)
        mask_bytes = base64.b64decode(_fix_b64_padding(raw))
        nparr = np.frombuffer(mask_bytes, np.uint8)
        mask_img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        if mask_img is None:
            continue
        if combined is None:
            combined = mask_img
        else:
            if combined.shape != mask_img.shape:
                mask_img = cv2.resize(mask_img, (combined.shape[1], combined.shape[0]))
            combined = cv2.bitwise_or(combined, mask_img)

    if combined is None:
        raise ValueError("No valid masks to combine")

    combined = (combined > 127).astype(np.uint8) * 255
    _, buffer = cv2.imencode(".png", combined)
    return f"data:image/png;base64,{base64.b64encode(buffer).decode('utf-8')}"


def dilate_mask(mask_b64: str, kernel_size: int = 21, iterations: int = 2) -> str:
    """Dilate (expand) a binary mask to cover edges and thin features.

    Args:
        mask_b64: Base64 data URI of binary mask.
        kernel_size: Size of the dilation kernel.
        iterations: Number of dilation passes.

    Returns:
        Dilated mask as base64 data URI.
    """
    import cv2
    import numpy as np

    raw = _strip_data_uri(mask_b64)
    mask_bytes = base64.b64decode(_fix_b64_padding(raw))
    nparr = np.frombuffer(mask_bytes, np.uint8)
    mask = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return mask_b64

    mask = (mask > 127).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    dilated = cv2.dilate(mask, kernel, iterations=iterations)

    _, buffer = cv2.imencode(".png", dilated)
    return f"data:image/png;base64,{base64.b64encode(buffer).decode('utf-8')}"


def _keep_object(obj: dict, image_height: int) -> bool:
    """Return True if the object should be kept (used for mask filtering).

    Filters out:
    - Bottom detections (likely curtain/false positives): center_y > 75% of height
    - Top detections (face/hair): center_y < 5% of height
    - Extremely wide boxes: width > 3x height
    """
    bbox = obj.get("bbox", [0, 0, 0, 0])
    x1, y1, x2, y2 = bbox
    center_y = (y1 + y2) / 2
    bbox_width = x2 - x1
    bbox_height = y2 - y1

    if center_y > image_height * 0.75:
        logger.info("Filtered %s at center_y=%d (bottom 25%%)", obj.get("class_name"), center_y)
        return False
    if center_y < image_height * 0.05:
        logger.info("Filtered %s at center_y=%d (top 5%%)", obj.get("class_name"), center_y)
        return False
    if bbox_height > 0 and bbox_width > 3.0 * bbox_height:
        logger.info("Filtered %s (bbox too wide: %dx%d)", obj.get("class_name"), bbox_width, bbox_height)
        return False
    return True


def _color_transfer(result_bytes: bytes, original_bytes: bytes, mask_b64: str) -> bytes:
    """Match mean color of inpainted region to surrounding skin.

    Computes mean BGR of the inpainted region and the surrounding unmasked
    border, then shifts the inpainted pixels to match the surrounding tone.
    """
    import cv2
    import numpy as np

    orig = cv2.imdecode(np.frombuffer(original_bytes, np.uint8), cv2.IMREAD_COLOR)
    result = cv2.imdecode(np.frombuffer(result_bytes, np.uint8), cv2.IMREAD_COLOR)
    if orig is None or result is None or orig.shape != result.shape:
        return result_bytes

    raw = _strip_data_uri(mask_b64)
    mask_bytes = base64.b64decode(_fix_b64_padding(raw))
    mask = cv2.imdecode(np.frombuffer(mask_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return result_bytes

    mask_bin = (mask > 127).astype(np.uint8)
    h, w = mask_bin.shape

    # Get surrounding border (eroded mask subtracted from dilated mask)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    dilated = cv2.dilate(mask_bin, kernel, iterations=1)
    eroded = cv2.erode(mask_bin, kernel, iterations=1)
    border = (dilated - eroded).astype(bool)

    # Ensure mask is 3-channel for multiplication
    mask_3ch = mask_bin[:, :, None].astype(np.float32)

    inpainted_mean = result[mask_bin > 0].mean(axis=0) if (mask_bin > 0).any() else None
    border_mean = orig[border].mean(axis=0) if border.any() else None

    if inpainted_mean is None or border_mean is None:
        return result_bytes

    # Compute shift: push inpainted pixels toward surrounding color
    shift = border_mean - inpainted_mean
    shift_3ch = shift[np.newaxis, np.newaxis, :].astype(np.float32)

    # Apply shift with mask weight (full shift inside, gradual at edges)
    corrected = result.astype(np.float32) + shift_3ch * mask_3ch * 0.6
    corrected = np.clip(corrected, 0, 255).astype(np.uint8)

    # Preserve unmasked pixels exactly
    unmasked = (mask_bin == 0)[:, :, None]
    corrected = np.where(unmasked, orig, corrected)

    _, buf = cv2.imencode(".png", corrected)
    return buf.tobytes()


def filter_clothing_objects(objects: list[dict], image_height: int) -> list[dict]:
    return [obj for obj in objects if _keep_object(obj, image_height)]


async def _get_torso_mask(
    se10: "SE10Client",
    image_bytes: bytes,
    filename: str,
    image_height: int,
) -> str | None:
    """Detect person, subtract head region, return torso mask as data URI.

    Used as fallback when clothing detection gives poor coverage (< 5%).
    """
    import cv2
    import numpy as np

    resp = await se10.segment(
        image_bytes=image_bytes,
        filename=filename,
        classes="person, woman, man",
        box_threshold=0.30,
        text_threshold=0.25,
        mode="person",
    )
    if not resp.get("detected") or not resp.get("masks"):
        logger.warning("Person detection failed for torso fallback")
        return None

    objects = resp.get("objects", [])
    masks = resp.get("masks", [])
    if not objects or not masks:
        return None

    # Take the largest person mask
    best_idx = 0
    best_area = 0
    for i, obj in enumerate(objects):
        if obj.get("area_pct", 0) > best_area:
            best_area = obj["area_pct"]
            best_idx = i

    mask_b64 = masks[best_idx]
    raw = _strip_data_uri(mask_b64)
    mask_bytes_raw = base64.b64decode(_fix_b64_padding(raw))
    nparr = np.frombuffer(mask_bytes_raw, np.uint8)
    pmask = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    if pmask is None:
        return None

    binary = (pmask > 127).astype(np.uint8) * 255
    h, w = binary.shape

    # Get person bounding box from mask contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    px1, py1, pw, ph = cv2.boundingRect(largest)

    # Subtract head: top 22% of person bounding box
    head_h = int(ph * 0.22)
    head_mask = np.zeros_like(binary)
    head_mask[py1:py1 + head_h, px1:px1 + pw] = 255
    torso = cv2.bitwise_and(binary, cv2.bitwise_not(head_mask))

    coverage = (torso > 0).sum() / torso.size * 100
    logger.info("Torso mask: coverage=%.1f%%, head subtracted y=%d-%d", coverage, py1, py1 + head_h)

    _, buf = cv2.imencode(".png", torso)
    return f"data:image/png;base64,{base64.b64encode(buf).decode()}"


def post_process_blend(
    original_bytes: bytes,
    inpainted_bytes: bytes,
    mask_b64: str,
    blend_kernel: int = 51,
    original_weight: float = 0.15,
) -> bytes:
    """Alpha-blend inpainted result with original image for smoother transition.

    Args:
        original_bytes: Original image bytes.
        inpainted_bytes: Inpainted image bytes from SE8.
        mask_b64: Binary mask (data URI) indicating inpainted region.
        blend_kernel: Gaussian blur kernel size for soft mask edges.
        original_weight: How much of the original to preserve (0-1).

    Returns:
        Blended image as PNG bytes.
    """
    import cv2
    import numpy as np

    orig_arr = np.frombuffer(original_bytes, np.uint8)
    orig = cv2.imdecode(orig_arr, cv2.IMREAD_COLOR)
    if orig is None:
        return inpainted_bytes

    inp_arr = np.frombuffer(inpainted_bytes, np.uint8)
    inp = cv2.imdecode(inp_arr, cv2.IMREAD_COLOR)
    if inp is None:
        return inpainted_bytes

    if orig.shape != inp.shape:
        inp = cv2.resize(inp, (orig.shape[1], orig.shape[0]))

    raw = _strip_data_uri(mask_b64)
    mask_bytes = base64.b64decode(_fix_b64_padding(raw))
    mask_arr = np.frombuffer(mask_bytes, np.uint8)
    mask = cv2.imdecode(mask_arr, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return inpainted_bytes

    if orig.shape[:2] != mask.shape:
        mask = cv2.resize(mask, (orig.shape[1], orig.shape[0]))

    mask = (mask > 127).astype(np.uint8) * 255

    # Gaussian blur for soft edges
    k = blend_kernel if blend_kernel % 2 == 1 else blend_kernel + 1
    soft_mask = cv2.GaussianBlur(mask.astype(np.float32), (k, k), 0)
    soft_mask = soft_mask / 255.0

    # Alpha blend: inpainted area weighted by soft_mask, original everywhere else
    alpha = soft_mask[:, :, np.newaxis]
    blended = (inp.astype(np.float32) * alpha + orig.astype(np.float32) * (1.0 - alpha))
    blended = np.clip(blended, 0, 255).astype(np.uint8)

    # Preserve original pixels fully outside mask
    mask_binary = mask > 127
    outside_mask = ~mask_binary
    blended[outside_mask] = orig[outside_mask]

    _, buffer = cv2.imencode(".png", blended)
    return buffer.tobytes()


async def run_clothes_removal(job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
    mode = job.request.mode or "clothes"
    logger.info("Starting %s removal pipeline for job %s", mode, job.job_id)

    se10 = SE10Client()
    se8 = SE8Client()

    try:
        image_bytes = _decode_image(job.request.image)
        logger.info("Job %s: image decoded (%d bytes)", job.job_id, len(image_bytes))

        from PIL import Image as PILImage
        img = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        image_height = img.size[1]

        # === Stage 2: SE10 — Detect ===
        job.status = ClothesRemovalJobStatus.DETECTING
        job.update_stage("detecting", "processing", progress=10.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        effective_classes = job.request.classes or BEST_CLOTHING_CLASSES

        t0 = time.time()
        segment_result = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}.jpg",
            classes=effective_classes,
            box_threshold=job.request.box_threshold,
            text_threshold=0.05,
            mode="clothes",
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
            return

        objects = segment_result.get("objects", [])
        all_masks = segment_result.get("masks", [])

        # Filter objects AND their corresponding masks together
        filtered_objects = []
        filtered_masks = []
        for i, obj in enumerate(objects):
            if _keep_object(obj, image_height):
                filtered_objects.append(obj)
                if i < len(all_masks):
                    filtered_masks.append(all_masks[i])
        logger.info(
            "Job %s: filtered %d → %d objects",
            job.job_id, len(objects), len(filtered_objects),
        )

        if not filtered_masks:
            # Fallback: try person → torso mask when clothing detection fails
            logger.info("Job %s: no clothing masks after filtering, trying person→torso fallback", job.job_id)
            torso_mask = await _get_torso_mask(se10, image_bytes, f"{job.job_id}.jpg", image_height)
            if torso_mask:
                filtered_masks = [torso_mask]
                filtered_objects = [{"class_name": "person_torso", "area_pct": 0, "confidence": 0, "bbox": [0, 0, 0, 0]}]
                logger.info("Job %s: using person→torso fallback mask", job.job_id)
            else:
                job.status = ClothesRemovalJobStatus.FAILED
                job.error = "SE10 detected objects but all were filtered out, and person fallback failed"
                job.update_stage("detecting", "failed", error="All objects filtered + fallback failed")
                store.save_job(job.job_id, job.model_dump(mode="json"))
                return

        job.objects_detected = len(filtered_objects)
        job.update_stage("detecting", "completed", progress=100.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        # === Stage 3: Combine masks ===
        job.update_stage("inpainting", "processing", progress=10.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        combined_mask = combine_masks(filtered_masks)
        combined_mask = dilate_mask(combined_mask, kernel_size=21, iterations=2)
        logger.info("Job %s: combined %d filtered masks + dilated", job.job_id, len(filtered_masks))

        # Check mask coverage — if too low, try person→torso fallback
        import cv2 as _cv2
        import numpy as _np
        raw_mask = _strip_data_uri(combined_mask)
        mask_arr = _np.frombuffer(base64.b64decode(_fix_b64_padding(raw_mask)), _np.uint8)
        mask_img = _cv2.imdecode(mask_arr, _cv2.IMREAD_GRAYSCALE)
        if mask_img is not None:
            coverage = (mask_img > 127).sum() / mask_img.size * 100
            logger.info("Job %s: clothing mask coverage=%.1f%%", job.job_id, coverage)
            if coverage < 5.0:
                logger.info("Job %s: low coverage, trying person→torso fallback", job.job_id)
                torso_mask = await _get_torso_mask(se10, image_bytes, f"{job.job_id}.jpg", image_height)
                if torso_mask:
                    combined_mask = dilate_mask(torso_mask, kernel_size=21, iterations=2)
                    filtered_objects = [{"class_name": "person_torso", "area_pct": coverage, "confidence": 0, "bbox": [0, 0, 0, 0]}]
                    logger.info("Job %s: using person→torso mask (was %.1f%%)", job.job_id, coverage)

        # === Stage 4: SE8 — Inpainting ===
        image_b64 = _to_data_uri(base64.b64encode(image_bytes).decode("utf-8"), mime="image/jpeg")

        prompt = job.request.prompt or DEFAULT_CLOTHES_PROMPT
        negative_prompt = job.request.negative_prompt or DEFAULT_CLOTHES_NEGATIVE
        inpaint_respective_field = 0.85
        inpaint_strength = 0.70

        t1 = time.time()
        inpaint_result = await se8.inpaint(
            image_b64=image_b64,
            mask_b64=combined_mask,
            prompt=prompt,
            negative_prompt=negative_prompt,
            inpaint_strength=inpaint_strength,
            inpaint_respective_field=inpaint_respective_field,
        )
        inpaint_time = time.time() - t1
        logger.info("Job %s: SE8 inpainting completed in %.1fs", job.job_id, inpaint_time)

        if isinstance(inpaint_result, list) and len(inpaint_result) > 0:
            inpaint_result = inpaint_result[0]

        result_b64 = inpaint_result.get("base64", "") if isinstance(inpaint_result, dict) else ""
        if not result_b64:
            job.status = ClothesRemovalJobStatus.FAILED
            job.error = "SE8 returned empty result"
            job.update_stage("inpainting", "failed", error="Empty SE8 result")
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        # === Stage 5: Save result ===
        raw_decode = _strip_data_uri(result_b64)
        result_bytes = base64.b64decode(_fix_b64_padding(raw_decode))

        # === Stage 6: Color correction ===
        try:
            result_bytes = _color_transfer(result_bytes, image_bytes, combined_mask)
            logger.info("Job %s: color correction applied", job.job_id)
        except Exception as e:
            logger.warning("Job %s: color correction failed (%s), using raw result", job.job_id, e)

        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)
        result_path = os.path.join(output_dir, f"{job.job_id}_result.png")

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
