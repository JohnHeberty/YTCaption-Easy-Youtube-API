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

BEST_CLOTHING_CLASSES = (
    "spaghetti strap, camisole, top, blouse"
)

DEFAULT_CLOTHES_PROMPT = (
    "natural skin tone matching surrounding skin, seamless texture, "
    "photorealistic, professional photography, soft lighting"
)
DEFAULT_PERSON_PROMPT = (
    "natural skin texture matching surrounding skin tone, seamless blend, "
    "preserve original body shape and features, realistic skin, soft lighting"
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


def _erode_mask(mask_b64: str, kernel_size: int = 15, iterations: int = 1) -> str:
    """Erode (shrink) a binary mask."""
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
    eroded = cv2.erode(mask, kernel, iterations=iterations)

    _, buffer = cv2.imencode(".png", eroded)
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
    """Match color of inpainted region to surrounding skin using HSV color space.

    Uses smooth alpha blending to avoid mask edge artifacts.
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

    # Get border region for color reference
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    dilated = cv2.dilate(mask_bin, kernel, iterations=1)
    eroded = cv2.erode(mask_bin, kernel, iterations=1)
    border = (dilated - eroded).astype(bool)

    if not border.any() or not (mask_bin > 0).any():
        return result_bytes

    # Convert to HSV
    orig_hsv = cv2.cvtColor(orig, cv2.COLOR_BGR2HSV).astype(np.float32)
    result_hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype(np.float32)

    # Get median H and S from border (surrounding skin)
    mean_h = np.median(orig_hsv[border, 0])
    mean_s = np.median(orig_hsv[border, 1])

    mask_bool = mask_bin > 0
    if mask_bool.any():
        result_h_median = np.median(result_hsv[mask_bool, 0])
        h_shift = mean_h - result_h_median
        if abs(h_shift) > 90:
            h_shift -= 180 if h_shift > 0 else -180
        result_hsv[mask_bool, 0] = np.mod(result_hsv[mask_bool, 0] + h_shift, 180)

        result_s_median = np.median(result_hsv[mask_bool, 1])
        if result_s_median > 0:
            s_ratio = mean_s / result_s_median
            s_factor = 1.0 + (s_ratio - 1.0) * 0.3
            result_hsv[mask_bool, 1] = np.clip(result_hsv[mask_bool, 1] * s_factor, 0, 255)

    # Reconvert to BGR
    corrected = cv2.cvtColor(result_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # SMOOTH BLEND: use narrow Gaussian to feather edges only (avoid spreading)
    alpha_mask = mask_bin.astype(np.float32)
    alpha_mask = cv2.GaussianBlur(alpha_mask, (5, 5), 0)
    alpha_3ch = alpha_mask[:, :, np.newaxis]

    # Blend: corrected inside mask, original outside, narrow smooth transition
    blended = (corrected.astype(np.float32) * alpha_3ch +
               orig.astype(np.float32) * (1.0 - alpha_3ch))
    blended = np.clip(blended, 0, 255).astype(np.uint8)

    _, buf = cv2.imencode(".png", blended)
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

    # Subtract head: top 35% of person bounding box (increased from 22% to better preserve face)
    head_h = int(ph * 0.35)
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

    # Progressive mode: run 4 sequential passes
    if mode == "progressive":
        await _run_progressive(job, store)
        return

    # NSFW mode: dedicated full clothing removal
    if mode == "nsfw":
        await _run_nsfw(job, store)
        return

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

        # Use different classes based on mode
        if mode == "person":
            effective_classes = job.request.classes or "person, woman, man"
        else:
            effective_classes = job.request.classes or BEST_CLOTHING_CLASSES

        t0 = time.time()
        
        # For person mode, use torso mask (head subtracted) to preserve face
        if mode == "person":
            logger.info("Job %s: using torso mask (head subtracted) for person mode", job.job_id)
            
            # Use _get_torso_mask which subtracts the head region
            torso_mask = await _get_torso_mask(se10, image_bytes, f"{job.job_id}.jpg", image_height)
            
            if torso_mask:
                filtered_masks = [torso_mask]
                filtered_objects = [{"class_name": "person_torso", "area_pct": 0, "confidence": 0, "bbox": [0, 0, 0, 0]}]
                logger.info("Job %s: using torso mask (head subtracted)", job.job_id)
            else:
                logger.warning("Job %s: torso detection failed, trying full person mask", job.job_id)
                
                # Fallback to full person mask
                resp = await se10.segment(
                    image_bytes=image_bytes,
                    filename=f"{job.job_id}.jpg",
                    classes="person, woman, man",
                    box_threshold=0.20,
                    text_threshold=0.15,
                    mode="person",
                )
                
                if resp.get("detected") and resp.get("masks"):
                    objects = resp.get("objects", [])
                    masks = resp.get("masks", [])
                    
                    best_idx = 0
                    best_area = 0
                    for i, obj in enumerate(objects):
                        if obj.get("area_pct", 0) > best_area:
                            best_area = obj["area_pct"]
                            best_idx = i
                    
                    if best_idx < len(masks):
                        filtered_masks = [masks[best_idx]]
                        filtered_objects = [objects[best_idx]]
                        logger.info("Job %s: fallback to full person mask (area=%.1f%%)", job.job_id, best_area)
                    else:
                        filtered_masks = []
                        filtered_objects = []
                else:
                    filtered_masks = []
                    filtered_objects = []
                    logger.warning("Job %s: person detection failed", job.job_id)
        else:
            # Clothes mode: regular detection
            segment_result = await se10.segment(
                image_bytes=image_bytes,
                filename=f"{job.job_id}.jpg",
                classes=effective_classes,
                box_threshold=job.request.box_threshold,
                text_threshold=0.05,
                mode=mode,
                detector=job.request.detector,
            )
            objects = segment_result.get("objects", [])
            all_masks = segment_result.get("masks", [])
            
            # Filter objects
            sorted_pairs = [
                (i, obj) for i, obj in enumerate(objects)
                if _keep_object(obj, image_height) and obj.get("confidence", 0) >= 0.10
            ]
            sorted_pairs.sort(key=lambda p: p[1].get("confidence", 0), reverse=True)
            max_objects = min(3, len(sorted_pairs))
            
            filtered_objects = []
            filtered_masks = []
            for idx in range(max_objects):
                i, obj = sorted_pairs[idx]
                filtered_objects.append(obj)
                if i < len(all_masks):
                    filtered_masks.append(all_masks[i])
        logger.info(
            "Job %s: filtered to %d objects",
            job.job_id, len(filtered_objects),
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

        prompt = job.request.prompt or (DEFAULT_PERSON_PROMPT if mode == "person" else DEFAULT_CLOTHES_PROMPT)
        negative_prompt = job.request.negative_prompt or DEFAULT_CLOTHES_NEGATIVE
        inpaint_respective_field = 0.85

        # Dynamic denoise based on final mask coverage
        raw_final = _strip_data_uri(combined_mask)
        final_arr = _np.frombuffer(base64.b64decode(_fix_b64_padding(raw_final)), _np.uint8)
        final_mask = _cv2.imdecode(final_arr, _cv2.IMREAD_GRAYSCALE)
        final_pct = (final_mask > 127).sum() / final_mask.size * 100 if final_mask is not None else 0.0
        
        # Person mode: preserve original person, only remove clothing
        if mode == "person":
            # Lower denoise to preserve original features (face, body shape, skin)
            inpaint_strength = 0.70  # Same as clothes mode - preserves original
            # Minimal erosion for person mode — keep large masks
            if final_pct > 50.0:
                erode_or_dilate = -5
            elif final_pct > 30.0:
                erode_or_dilate = -8
            else:
                erode_or_dilate = -10
        else:
            inpaint_strength = 0.70  # Default for clothes mode
            # Dynamic erosion based on coverage
            if final_pct > 30.0:
                erode_or_dilate = -20
            elif final_pct > 15.0:
                erode_or_dilate = -15
            elif final_pct > 5.0:
                erode_or_dilate = -10
            else:
                erode_or_dilate = -5

        # Cap coverage at 15% ONLY for clothes mode — person mode keeps full mask
        if mode != "person" and final_pct > 15.0:
            logger.info("Job %s: coverage %.1f%% exceeds cap, eroding mask", job.job_id, final_pct)
            erode_or_dilate = min(erode_or_dilate, -30)
            erode_kern = max(int((final_pct - 15.0) * 3), 15)
            combined_mask = _erode_mask(combined_mask, kernel_size=erode_kern, iterations=2)
            raw_final2 = _strip_data_uri(combined_mask)
            final_arr2 = _np.frombuffer(base64.b64decode(_fix_b64_padding(raw_final2)), _np.uint8)
            final_mask2 = _cv2.imdecode(final_arr2, _cv2.IMREAD_GRAYSCALE)
            if final_mask2 is not None:
                final_pct = (final_mask2 > 127).sum() / final_mask2.size * 100

        logger.info("Job %s: final coverage=%.1f%%, denoise=%.2f, erode=%d", job.job_id, final_pct, inpaint_strength, erode_or_dilate)

        t1 = time.time()

        per_garment = getattr(job.request, "per_garment", False) and len(filtered_masks) > 1

        if per_garment:
            # Per-garment: inpaint each mask separately, merge results
            logger.info("Job %s: per-garment mode (%d masks)", job.job_id, len(filtered_masks))
            result_bytes_merge = image_bytes
            for mi, single_mask in enumerate(filtered_masks):
                logger.info("Job %s: inpainting garment %d/%d", job.job_id, mi + 1, len(filtered_masks))
                single_mask_dilated = dilate_mask(single_mask, kernel_size=21, iterations=2)
                single_b64 = _to_data_uri(base64.b64encode(result_bytes_merge).decode("utf-8"), mime="image/jpeg")
                single_result = await se8.inpaint(
                    image_b64=single_b64,
                    mask_b64=single_mask_dilated,
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    inpaint_strength=inpaint_strength,
                    inpaint_respective_field=inpaint_respective_field,
                    inpaint_erode_or_dilate=erode_or_dilate,
                )
                if isinstance(single_result, list) and len(single_result) > 0:
                    single_result = single_result[0]
                single_b64_out = single_result.get("base64", "") if isinstance(single_result, dict) else ""
                if single_b64_out:
                    raw_decode = _strip_data_uri(single_b64_out)
                    result_bytes_merge = base64.b64decode(_fix_b64_padding(raw_decode))
            result_bytes = result_bytes_merge
        else:
            # Single-pass: combine all masks into one inpaint
            inpaint_result = await se8.inpaint(
                image_b64=image_b64,
                mask_b64=combined_mask,
                prompt=prompt,
                negative_prompt=negative_prompt,
                inpaint_strength=inpaint_strength,
                inpaint_respective_field=inpaint_respective_field,
                inpaint_erode_or_dilate=erode_or_dilate,
            )
            if isinstance(inpaint_result, list) and len(inpaint_result) > 0:
                inpaint_result = inpaint_result[0]

            result_b64 = inpaint_result.get("base64", "") if isinstance(inpaint_result, dict) else ""
            if not result_b64:
                job.status = ClothesRemovalJobStatus.FAILED
                job.error = "SE8 returned empty result"
                job.update_stage("inpainting", "failed", error="Empty SE8 result")
                store.save_job(job.job_id, job.model_dump(mode="json"))
                return

            raw_decode = _strip_data_uri(result_b64)
            result_bytes = base64.b64decode(_fix_b64_padding(raw_decode))

        inpaint_time = time.time() - t1
        logger.info("Job %s: SE8 inpainting completed in %.1fs (per_garment=%s)", job.job_id, inpaint_time, per_garment)

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

        # Webhook notification
        webhook_url = getattr(job.request, "webhook_url", None)
        if webhook_url:
            try:
                import httpx as _httpx
                async with _httpx.AsyncClient(timeout=10) as wh:
                    await wh.post(webhook_url, json={
                        "job_id": job.job_id,
                        "status": "completed",
                        "result_path": result_path,
                        "objects_detected": job.objects_detected,
                    })
                logger.info("Job %s: webhook sent to %s", job.job_id, webhook_url)
            except Exception as e:
                logger.warning("Job %s: webhook failed (%s)", job.job_id, e)

    except Exception as e:
        logger.error("Job %s failed: %s", job.job_id, e, exc_info=True)
        job.status = ClothesRemovalJobStatus.FAILED
        job.error = str(e)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

    finally:
        await se10.close()
        await se8.close()


# =============================================================================
# Progressive mode: 4-pass clothing removal
# =============================================================================

PROGRESSIVE_PASSES = [
    {"classes": "spaghetti strap, camisole", "box_threshold": 0.06, "text_threshold": 0.04, "inpaint_strength": 0.65, "detector": "florence2", "name": "straps", "se_mode": "clothes"},
    {"classes": "top, blouse, shirt", "box_threshold": 0.08, "text_threshold": 0.05, "inpaint_strength": 0.60, "detector": "florence2", "name": "top", "se_mode": "clothes"},
    {"classes": "dress, clothing, garment", "box_threshold": 0.10, "text_threshold": 0.07, "inpaint_strength": 0.55, "detector": "florence2", "name": "full", "se_mode": "clothes"},
    {"classes": "fabric, textile, outfit", "box_threshold": 0.12, "text_threshold": 0.09, "inpaint_strength": 0.50, "detector": "florence2", "name": "cleanup", "se_mode": "clothes"},
]

PROGRESSIVE_PASSES_PERSON = [
    {"classes": "spaghetti strap, camisole", "box_threshold": 0.06, "text_threshold": 0.04, "inpaint_strength": 0.65, "detector": "florence2", "name": "straps", "se_mode": "clothes"},
    {"classes": "top, blouse, shirt, clothing", "box_threshold": 0.08, "text_threshold": 0.05, "inpaint_strength": 0.60, "detector": "florence2", "name": "top", "se_mode": "clothes"},
    {"classes": "dress, skirt, clothing, garment, fabric", "box_threshold": 0.10, "text_threshold": 0.07, "inpaint_strength": 0.55, "detector": "florence2", "name": "full", "se_mode": "clothes"},
    {"classes": "person, woman, man", "box_threshold": 0.15, "text_threshold": 0.10, "inpaint_strength": 0.50, "detector": "groundingdino", "name": "person-cleanup", "se_mode": "person"},
]


async def _run_progressive(job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
    """Run 4-pass progressive clothing removal."""
    se10 = SE10Client()
    se8 = SE8Client()

    try:
        image_bytes = _decode_image(job.request.image)
        logger.info("Job %s: progressive mode — image decoded (%d bytes)", job.job_id, len(image_bytes))

        current_bytes = image_bytes

        # Select pass config based on job classes
        job_classes = (job.request.classes or "").lower()
        if "person" in job_classes or "woman" in job_classes:
            passes = PROGRESSIVE_PASSES_PERSON
        else:
            passes = PROGRESSIVE_PASSES
        total_passes = len(passes)

        for pass_idx, pass_config in enumerate(passes):
            progress = ((pass_idx + 1) / total_passes) * 90
            job.update_stage("inpainting", "processing", progress=progress)
            store.save_job(job.job_id, job.model_dump(mode="json"))

            logger.info("Job %s: pass %d/%d — %s (classes=%s, denoise=%.2f, mode=%s)",
                job.job_id, pass_idx + 1, total_passes, pass_config["name"],
                pass_config["classes"], pass_config["inpaint_strength"], pass_config.get("se_mode", "clothes"))

            # SE10 detection
            t0 = time.time()
            segment_result = await se10.segment(
                image_bytes=current_bytes,
                filename=f"{job.job_id}_pass{pass_idx}.jpg",
                classes=pass_config["classes"],
                box_threshold=pass_config["box_threshold"],
                text_threshold=pass_config["text_threshold"],
                mode=pass_config.get("se_mode", "clothes"),
                detector=pass_config["detector"],
            )
            seg_time = time.time() - t0

            objects = segment_result.get("objects", [])
            all_masks = segment_result.get("masks", [])

            if not segment_result.get("detected") or not all_masks:
                logger.info("Job %s: pass %d — no detection, skipping", job.job_id, pass_idx + 1)
                continue

            # Filter objects — include all detections above min confidence
            sorted_pairs = [
                (i, obj) for i, obj in enumerate(objects)
                if obj.get("confidence", 0) >= 0.05
            ]
            sorted_pairs.sort(key=lambda p: p[1].get("confidence", 0), reverse=True)

            filtered_masks = []
            for i, obj in sorted_pairs[:5]:
                if i < len(all_masks):
                    filtered_masks.append(all_masks[i])

            if not filtered_masks:
                logger.info("Job %s: pass %d — no masks after filtering", job.job_id, pass_idx + 1)
                continue

            logger.info("Job %s: pass %d — %d masks, detection %.1fs",
                job.job_id, pass_idx + 1, len(filtered_masks), seg_time)

            # Combine and dilate masks — standard dilation
            combined_mask = combine_masks(filtered_masks)
            combined_mask = dilate_mask(combined_mask, kernel_size=21, iterations=2)

            # Protect face region — skip inpainting if mask covers face (top 30%)
            import cv2 as _cv2p
            import numpy as _npp
            raw_mask = _strip_data_uri(combined_mask)
            mask_arr = _npp.frombuffer(base64.b64decode(_fix_b64_padding(raw_mask)), _npp.uint8)
            mask_img = _cv2p.imdecode(mask_arr, _cv2p.IMREAD_GRAYSCALE)
            if mask_img is not None:
                h_img = mask_img.shape[0]
                face_region = mask_img[:int(h_img * 0.30)]
                face_coverage = (face_region > 127).sum() / max(face_region.size, 1) * 100
                if face_coverage > 5.0:
                    logger.warning("Job %s: pass %d — mask covers %.1f%% of face region, eroding top", job.job_id, pass_idx + 1, face_coverage)
                    # Zero out face region from mask
                    mask_img[:int(h_img * 0.30)] = 0
                    _, buf = _cv2p.imencode(".png", mask_img)
                    combined_mask = _to_data_uri(base64.b64encode(buf).decode("utf-8"), mime="image/png")

            # SE8 inpainting
            current_b64 = _to_data_uri(base64.b64encode(current_bytes).decode("utf-8"), mime="image/jpeg")

            result = await se8.inpaint(
                image_b64=current_b64,
                mask_b64=combined_mask,
                prompt=DEFAULT_PERSON_PROMPT,
                negative_prompt=DEFAULT_CLOTHES_NEGATIVE,
                inpaint_strength=pass_config["inpaint_strength"],
                inpaint_respective_field=0.85,
                inpaint_erode_or_dilate=-10,
            )

            if result and result.get("base64"):
                result_bytes = base64.b64decode(result["base64"])
                current_bytes = result_bytes
                logger.info("Job %s: pass %d — inpainting completed", job.job_id, pass_idx + 1)

        # Save final result
        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)
        result_path = os.path.join(output_dir, f"{job.job_id}_result.png")

        with open(result_path, "wb") as f:
            f.write(current_bytes)

        job.result_path = result_path
        job.status = ClothesRemovalJobStatus.COMPLETED
        job.progress = 100.0
        job.objects_detected = total_passes
        job.update_stage("inpainting", "completed", progress=100.0)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

        logger.info("Job %s: progressive completed — %d passes, result saved to %s",
            job.job_id, total_passes, result_path)

    except Exception as e:
        logger.error("Job %s progressive failed: %s", job.job_id, e, exc_info=True)
        job.status = ClothesRemovalJobStatus.FAILED
        job.error = str(e)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

    finally:
        await se10.close()
        await se8.close()


# =============================================================================
# NSFW mode: full clothing removal (single pass, high denoise)
# =============================================================================

NSFW_NEGATIVE = (
    "clothes, clothing, fabric, bra, straps, underwear, top, blouse, shirt, "
    "dress, skirt, pants, shorts, swimsuit, bikini, lingerie, textile, garment, "
    "text, watermark, deformed, blurry, bad anatomy, bad proportions, "
    "extra limbs, disfigured, poorly drawn face, mutated hands, extra fingers"
)

NSFW_PROMPT = (
    "bare skin, exposed skin, natural realistic skin texture, "
    "seamless transition with surrounding skin, photorealistic, "
    "soft lighting, professional photography"
)


async def _run_nsfw(job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
    """Dedicated NSFW: clothes detection → only clothing mask → replace with skin.

    Key: detects CLOTHES (not person), so only clothing areas are inpainted.
    Body parts outside the mask remain untouched.
    """
    import cv2 as _cv2
    import numpy as _np

    se10 = SE10Client()
    se8 = SE8Client()

    try:
        image_bytes = _decode_image(job.request.image)
        from PIL import Image as PILImage
        img = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        image_height = img.size[1]

        # Stage 1: Detect CLOTHING (not person!)
        job.status = ClothesRemovalJobStatus.DETECTING
        job.update_stage("detecting", "processing", progress=10.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        t0 = time.time()
        segment_result = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}.jpg",
            classes="spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment",
            box_threshold=0.08,
            text_threshold=0.05,
            mode="clothes",
            detector="florence2",
        )
        seg_time = time.time() - t0

        if not segment_result.get("detected") or not segment_result.get("masks"):
            logger.warning("Job %s: NSFW — no clothing detected", job.job_id)
            job.status = ClothesRemovalJobStatus.COMPLETED
            job.error = "No clothing detected in image"
            job.progress = 100.0
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        objects = segment_result.get("objects", [])
        masks = segment_result.get("masks", [])

        logger.info("Job %s: NSFW — %d clothing items detected in %.1fs",
            job.job_id, len(objects), seg_time)

        # Combine ALL clothing masks (no filtering — we want full coverage)
        all_combined = None
        for mask_b64 in masks:
            raw = _strip_data_uri(mask_b64)
            mask_bytes_raw = base64.b64decode(_fix_b64_padding(raw))
            m = _cv2.imdecode(_np.frombuffer(mask_bytes_raw, _np.uint8), _cv2.IMREAD_GRAYSCALE)
            if m is None:
                continue
            if all_combined is None:
                all_combined = (m > 127).astype(_np.uint8) * 255
            else:
                if all_combined.shape != m.shape:
                    m = _cv2.resize(m, (all_combined.shape[1], all_combined.shape[0]))
                all_combined = _cv2.bitwise_or(all_combined, (m > 127).astype(_np.uint8) * 255)

        if all_combined is None:
            logger.error("Job %s: NSFW — failed to combine masks", job.job_id)
            job.status = ClothesRemovalJobStatus.FAILED
            job.error = "Failed to combine masks"
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        # NO dilation — keep mask exactly as detected to avoid touching background
        _, mask_buf = _cv2.imencode(".png", all_combined)
        nsfw_mask_b64 = _to_data_uri(base64.b64encode(mask_buf).decode("utf-8"), mime="image/png")

        logger.info("Job %s: NSFW — combined mask ready (%.1f%% coverage)",
            job.job_id, (all_combined > 0).sum() / all_combined.size * 100)

        # Stage 2: Inpaint ONLY the clothing mask area
        job.update_stage("detecting", "completed", progress=100.0)
        job.update_stage("inpainting", "processing", progress=30.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        image_b64 = _to_data_uri(base64.b64encode(image_bytes).decode("utf-8"), mime="image/jpeg")

        t1 = time.time()
        result = await se8.inpaint(
            image_b64=image_b64,
            mask_b64=nsfw_mask_b64,
            prompt=NSFW_PROMPT,
            negative_prompt=NSFW_NEGATIVE,
            inpaint_strength=0.65,
            inpaint_respective_field=0.85,
            inpaint_erode_or_dilate=-8,
            loras=[
                {"enabled": True, "model_name": "NsfwPovAllInOneLoraSdxl-000009.safetensors", "weight": 0.5},
                {"enabled": True, "model_name": "sd_xl_offset_example-lora_1.0.safetensors", "weight": 0.1},
                {"enabled": True, "model_name": "add-detail-xl.safetensors", "weight": 0.8},
                {"enabled": True, "model_name": "None", "weight": 1.0},
                {"enabled": True, "model_name": "None", "weight": 1.0},
            ],
        )
        inpaint_time = time.time() - t1

        if not result or not result.get("base64"):
            logger.error("Job %s: NSFW — SE8 failed", job.job_id)
            job.status = ClothesRemovalJobStatus.FAILED
            job.error = "SE8 returned empty"
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        result_bytes = base64.b64decode(result["base64"])
        logger.info("Job %s: NSFW — inpainting done in %.1fs", job.job_id, inpaint_time)

        # Stage 3: HARD COMPOSITE — original outside mask, inpainted inside mask ONLY
        # This guarantees nothing outside the clothing mask is changed
        job.update_stage("inpainting", "processing", progress=80.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        try:
            orig_img = _cv2.imdecode(_np.frombuffer(image_bytes, _np.uint8), _cv2.IMREAD_COLOR)
            result_img = _cv2.imdecode(_np.frombuffer(result_bytes, _np.uint8), _cv2.IMREAD_COLOR)

            if orig_img is not None and result_img is not None:
                # Resize result to match original if SE8 changed dimensions
                if result_img.shape != orig_img.shape:
                    result_img = _cv2.resize(result_img, (orig_img.shape[1], orig_img.shape[0]))
                    logger.info("Job %s: NSFW — resized result to match original %s", job.job_id, str(orig_img.shape))

                # Decode mask
                raw_m = _strip_data_uri(nsfw_mask_b64)
                mask_bytes_m = base64.b64decode(_fix_b64_padding(raw_m))
                mask_arr = _cv2.imdecode(_np.frombuffer(mask_bytes_m, _np.uint8), _cv2.IMREAD_GRAYSCALE)

                if mask_arr is not None:
                    if mask_arr.shape != orig_img.shape[:2]:
                        mask_arr = _cv2.resize(mask_arr, (orig_img.shape[1], orig_img.shape[0]))

                    # Feather edge: 5px Gaussian on mask boundary for smooth transition
                    mask_f = mask_arr.astype(_np.float32) / 255.0
                    mask_f = _cv2.GaussianBlur(mask_f, (5, 5), 0)
                    mask_3ch = mask_f[:, :, _np.newaxis]

                    # Composite: inpainted inside mask, original outside
                    composited = (result_img.astype(_np.float32) * mask_3ch +
                                  orig_img.astype(_np.float32) * (1.0 - mask_3ch))
                    composited = _np.clip(composited, 0, 255).astype(_np.uint8)
                    _, buf = _cv2.imencode(".png", composited)
                    result_bytes = buf.tobytes()
                    logger.info("Job %s: NSFW — hard composite applied", job.job_id)
        except Exception as e:
            logger.warning("Job %s: NSFW — composite failed (%s)", job.job_id, e)

        # Save
        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)
        result_path = os.path.join(output_dir, f"{job.job_id}_result.png")

        with open(result_path, "wb") as f:
            f.write(result_bytes)

        job.result_path = result_path
        job.status = ClothesRemovalJobStatus.COMPLETED
        job.progress = 100.0
        job.objects_detected = len(objects)
        job.update_stage("inpainting", "completed", progress=100.0)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

        logger.info("Job %s: NSFW completed — %s", job.job_id, result_path)

    except Exception as e:
        logger.error("Job %s NSFW failed: %s", job.job_id, e, exc_info=True)
        job.status = ClothesRemovalJobStatus.FAILED
        job.error = str(e)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

    finally:
        await se10.close()
        await se8.close()
