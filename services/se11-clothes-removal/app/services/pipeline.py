"""Pipeline for SE11 Clothes Removal — orchestrates SE10 → SE8 → post-process."""
from __future__ import annotations

import asyncio
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
    "NSFW, NSFW, NSFW, NSFW, NSFW, "
    "bare skin, smooth skin surface, realistic skin texture, "
    "detailed breast anatomy, realistic nipples, natural skin pores, "
    "seamless skin transition, consistent skin tone with surrounding body, "
    "photorealistic, professional photography, studio lighting, "
    "high resolution, sharp focus on skin detail, 8k uhd, "
    "hyperrealistic, detailed skin rendering, natural body proportions"
)
DEFAULT_PERSON_PROMPT = (
    "natural skin texture matching surrounding skin tone, seamless blend, "
    "preserve original body shape and features, realistic skin, soft lighting"
)
DEFAULT_CLOTHES_NEGATIVE = (
    "clothes, fabric, bra, straps, underwear, top, blouse, shirt, "
    "dress, skirt, pattern, floral, textile, garment, "
    "text, watermark, deformed, blurry, cartoon, anime, painting, CGI, "
    "extra limbs, disfigured, poorly drawn face, mutated hands, "
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


def _color_transfer(result_bytes: bytes, original_bytes: bytes, mask_b64: str, reference_mask=None) -> bytes:
    """Match color of inpainted region to exposed skin using HSV color space.

    Uses smooth alpha blending. If reference_mask is provided, uses exposed skin
    pixels as color reference instead of border region.
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

    # Get reference pixels for color matching
    orig_hsv = cv2.cvtColor(orig, cv2.COLOR_BGR2HSV).astype(np.float32)
    result_hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype(np.float32)

    if reference_mask is not None and (reference_mask > 0).any():
        # Use exposed skin as reference (most accurate)
        ref_pixels = orig_hsv[reference_mask > 0]
        mean_h = np.median(ref_pixels[:, 0])
        mean_s = np.median(ref_pixels[:, 1])
    else:
        # Fallback: border region
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
        dilated = cv2.dilate(mask_bin, kernel, iterations=1)
        eroded = cv2.erode(mask_bin, kernel, iterations=1)
        border = (dilated - eroded).astype(bool)
        if not border.any():
            return result_bytes
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

    corrected = cv2.cvtColor(result_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    alpha_mask = mask_bin.astype(np.float32)
    alpha_mask = cv2.GaussianBlur(alpha_mask, (5, 5), 0)
    alpha_3ch = alpha_mask[:, :, np.newaxis]

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

    # NSFW mode: OFFICIAL — routes to v15 pipeline (body mask + juggernautXL)
    if mode == "nsfw":
        logger.info("Job %s: using OFFICIAL NSFW pipeline (v15 body_mask)", job.job_id)
        await _run_pipe_nsfw_3layers_max(job, store)
        return

    # NSFW TEST mode: PLAN-1 (clothing exact + 20px dilation) — NOT production
    if mode == "nsfw_test":
        logger.info("Job %s: using TEST NSFW pipeline (PLAN-1 clothing_exact + 20px)", job.job_id)
        await _run_nsfw_test(job, store)
        return

    # Pipe NSFW: multi-stage (progressive + upscale) — DEPRECATED
    if mode == "pipe_nsfw":
        logger.warning("Job %s: mode 'pipe_nsfw' DEPRECATED, use 'nsfw' instead", job.job_id)
        await _run_pipe_nsfw(job, store)
        return

    # Pipe NSFW subtract: person - face - background = clothing area — DEPRECATED
    if mode == "pipe_nsfw_subtract":
        logger.warning("Job %s: mode 'pipe_nsfw_subtract' DEPRECATED, use 'nsfw' instead", job.job_id)
        await _run_pipe_nsfw_subtract(job, store)
        return

    # Pipe NSFW 3-layers: face+head+bg preserved, body isolated, clothes detected — DEPRECATED
    if mode == "pipe_3layers":
        logger.warning("Job %s: mode 'pipe_3layers' DEPRECATED, use 'nsfw' instead", job.job_id)
        await _run_pipe_nsfw_3layers(job, store)
        return

    # Pipe NSFW 3layers_max: alias for 'nsfw' — DEPRECATED (use 'nsfw')
    if mode == "pipe_3layers_max":
        logger.warning("Job %s: mode 'pipe_3layers_max' DEPRECATED, use 'nsfw' instead", job.job_id)
        await _run_pipe_nsfw_3layers_max(job, store)
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
    "bare skin, no clothing, naked body, natural realistic skin texture, "
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
            classes="spaghetti strap, camisole, top, blouse, shirt, dress",
            box_threshold=0.10,
            text_threshold=0.08,
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

        # Filter: keep only objects with area > 0.5% (remove tiny false positives)
        filtered_pairs = [(i, obj) for i, obj in enumerate(objects) if obj.get("area_pct", 0) > 0.5]
        if not filtered_pairs:
            filtered_pairs = [(i, obj) for i, obj in enumerate(objects)]

        logger.info("Job %s: NSFW — %d/%d clothing items detected in %.1fs",
            job.job_id, len(filtered_pairs), len(objects), seg_time)

        # Combine filtered clothing masks
        all_combined = None
        for i, obj in filtered_pairs:
            if i >= len(masks):
                continue
            mask_b64 = masks[i]
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


# =============================================================================
# Pipe NSFW: progressive → person mask composite → morphological blend → upscale
# =============================================================================

async def _run_pipe_nsfw(job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
    """Multi-stage NSFW pipeline:
    1. Progressive clothes removal (v83 best quality)
    2. Detect person in ORIGINAL → person mask
    3. Composite: paste NSFW result INSIDE person mask over original (background preserved)
    4. Morphological opening/closing → smooth paste edges
    5. SE8 upscale 2x → enhance details, remove artifacts
    """
    import cv2 as _cv2
    import numpy as _np

    se10 = SE10Client()
    se8 = SE8Client()

    try:
        image_bytes = _decode_image(job.request.image)
        logger.info("Job %s: pipe_nsfw started", job.job_id)

        # Decode original
        orig_img = _cv2.imdecode(_np.frombuffer(image_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if orig_img is None:
            raise ValueError("Failed to decode original image")
        orig_h, orig_w = orig_img.shape[:2]
        current_bytes = image_bytes

        # === Stage 1: Single-pass clothes detection + inpainting with NSFW ===
        job.update_stage("inpainting", "processing", progress=5.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        nsfw_loras = [
            {"enabled": True, "model_name": "NsfwPovAllInOneLoraSdxl-000009.safetensors", "weight": 0.5},
            {"enabled": True, "model_name": "sd_xl_offset_example-lora_1.0.safetensors", "weight": 0.1},
            {"enabled": True, "model_name": "add-detail-xl.safetensors", "weight": 0.8},
            {"enabled": True, "model_name": "None", "weight": 1.0},
            {"enabled": True, "model_name": "None", "weight": 1.0},
        ]

        # Single pass: detect all clothing classes with low threshold
        seg_result = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}_clothes.jpg",
            classes="spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment, fabric, textile",
            box_threshold=0.04,
            text_threshold=0.03,
            mode="clothes",
            detector="florence2",
        )

        objects = seg_result.get("objects", [])
        all_masks = seg_result.get("masks", [])

        if seg_result.get("detected") and all_masks:
            sorted_pairs = [(i, obj) for i, obj in enumerate(objects) if obj.get("confidence", 0) >= 0.03]
            sorted_pairs.sort(key=lambda p: p[1].get("confidence", 0), reverse=True)
            filtered_masks = [all_masks[i] for i, _ in sorted_pairs[:15] if i < len(all_masks)]

            if filtered_masks:
                combined_mask = combine_masks(filtered_masks)
                combined_mask = dilate_mask(combined_mask, kernel_size=11, iterations=1)

                # CRITICAL: Zero face region from mask BEFORE sending to SE8
                raw_cm = _strip_data_uri(combined_mask)
                cm_bytes = base64.b64decode(_fix_b64_padding(raw_cm))
                cm_arr = _cv2.imdecode(_np.frombuffer(cm_bytes, _np.uint8), _cv2.IMREAD_GRAYSCALE)
                if cm_arr is not None:
                    face_cutoff = int(cm_arr.shape[0] * 0.35)
                    cm_arr[:face_cutoff, :] = 0
                    _, cm_buf = _cv2.imencode(".png", cm_arr)
                    combined_mask = _to_data_uri(base64.b64encode(cm_buf).decode("utf-8"), mime="image/png")
                    logger.info("Job %s: face region zeroed in SE8 mask", job.job_id)

                current_b64 = _to_data_uri(base64.b64encode(image_bytes).decode("utf-8"), mime="image/jpeg")
                result = await se8.inpaint(
                    image_b64=current_b64,
                    mask_b64=combined_mask,
                    prompt=NSFW_PROMPT,
                    negative_prompt=NSFW_NEGATIVE,
                    inpaint_strength=0.70,
                    inpaint_respective_field=0.85,
                    inpaint_erode_or_dilate=-10,
                    loras=nsfw_loras,
                    base_model="lustifySDXLNSFW_v20-inpainting.safetensors",
                )
                if result and result.get("base64"):
                    current_bytes = base64.b64decode(result["base64"])

        # Decode progressive result
        nsfw_img = _cv2.imdecode(_np.frombuffer(current_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if nsfw_img is None:
            raise ValueError("Failed to decode progressive result")
        if nsfw_img.shape[:2] != (orig_h, orig_w):
            nsfw_img = _cv2.resize(nsfw_img, (orig_w, orig_h))

        logger.info("Job %s: Stage 1 done — progressive clothes removal", job.job_id)

        # === Stage 2: Detect person in ORIGINAL → person mask ===
        job.update_stage("inpainting", "processing", progress=45.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        person_seg = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}_person.jpg",
            classes="person, woman, man",
            box_threshold=0.20,
            text_threshold=0.15,
            mode="person",
        )

        if person_seg.get("detected") and person_seg.get("masks"):
            # Take the largest person mask
            p_objects = person_seg.get("objects", [])
            p_masks = person_seg.get("masks", [])
            best_idx = 0
            best_area = 0
            for i, obj in enumerate(p_objects):
                if obj.get("area_pct", 0) > best_area:
                    best_area = obj["area_pct"]
                    best_idx = i

            if best_idx < len(p_masks):
                raw_p = _strip_data_uri(p_masks[best_idx])
                p_mask_bytes = base64.b64decode(_fix_b64_padding(raw_p))
                person_mask = _cv2.imdecode(_np.frombuffer(p_mask_bytes, _np.uint8), _cv2.IMREAD_GRAYSCALE)

                if person_mask is not None:
                    if person_mask.shape[:2] != (orig_h, orig_w):
                        person_mask = _cv2.resize(person_mask, (orig_w, orig_h))

                    person_binary = (person_mask > 127).astype(_np.uint8) * 255

                    # CRITICAL: Zero top 40% of mask to protect face
                    face_cutoff = int(orig_h * 0.40)
                    person_binary[:face_cutoff, :] = 0

                    logger.info("Job %s: Stage 2 — person mask detected (%.1f%% coverage, face protected)",
                        job.job_id, (person_binary > 0).sum() / person_binary.size * 100)

                    # === Stage 3: Composite NSFW inside person mask over original ===
                    job.update_stage("inpainting", "processing", progress=60.0)
                    store.save_job(job.job_id, job.model_dump(mode="json"))

                    # Soft mask: feather edges for smooth blending
                    soft_mask = person_binary.astype(_np.float32) / 255.0
                    soft_mask = _cv2.GaussianBlur(soft_mask, (15, 15), 0)
                    soft_3ch = soft_mask[:, :, _np.newaxis]

                    # Composite: NSFW inside person, original outside
                    composited = (nsfw_img.astype(_np.float32) * soft_3ch +
                                  orig_img.astype(_np.float32) * (1.0 - soft_3ch))
                    composited = _np.clip(composited, 0, 255).astype(_np.uint8)

                    logger.info("Job %s: Stage 3 — composite done", job.job_id)

                    # === Stage 4: Gentle edge softening ===
                    job.update_stage("inpainting", "processing", progress=70.0)
                    store.save_job(job.job_id, job.model_dump(mode="json"))

                    # Bilateral filter on mask edges for smooth transition
                    edge_mask = _cv2.Canny(_cv2.cvtColor(composited, _cv2.COLOR_BGR2GRAY), 30, 100)
                    edge_mask = _cv2.dilate(edge_mask, _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)
                    if (edge_mask > 0).any():
                        smoothed = _cv2.bilateralFilter(composited, 5, 50, 50)
                        composited[edge_mask > 0] = smoothed[edge_mask > 0]

                    logger.info("Job %s: Stage 4 — edge softening done", job.job_id)

                    nsfw_img = composited
                else:
                    logger.warning("Job %s: person mask decode failed, using progressive result", job.job_id)
            else:
                logger.warning("Job %s: no person mask, using progressive result", job.job_id)
        else:
            logger.warning("Job %s: no person detected, using progressive result", job.job_id)

        # === Save final (NO upscaler — it destroys results) ===
        job.update_stage("inpainting", "processing", progress=90.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        # === Stage 5: Face restore (skip for now — GFPGAN needs separate service) ===
        logger.info("Job %s: Stage 5 — face restore skipped (pending GFPGAN integration)", job.job_id)

        # === Save final ===
        _, final_buf = _cv2.imencode(".png", nsfw_img)
        final_bytes = final_buf.tobytes()

        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)
        result_path = os.path.join(output_dir, f"{job.job_id}_result.png")
        with open(result_path, "wb") as f:
            f.write(final_bytes)

        job.result_path = result_path
        job.status = ClothesRemovalJobStatus.COMPLETED
        job.progress = 100.0
        job.objects_detected = len(PROGRESSIVE_PASSES)
        job.update_stage("inpainting", "completed", progress=100.0)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))
        logger.info("Job %s: pipe_nsfw completed — %s", job.job_id, result_path)

    except Exception as e:
        logger.error("Job %s pipe_nsfw failed: %s", job.job_id, e, exc_info=True)
        job.status = ClothesRemovalJobStatus.FAILED
        job.error = str(e)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

    finally:
        await se10.close()
        await se8.close()


# =============================================================================
# Pipe NSFW Subtract: person - face - background = clothing mask only
# =============================================================================

NSFW_SUBTRACT_PROMPT = (
    "natural skin texture matching surrounding skin tone, realistic bare skin, "
    "seamless blend, photorealistic, soft lighting"
)

NSFW_SUBTRACT_NEGATIVE = (
    "clothes, clothing, fabric, bra, straps, underwear, top, blouse, shirt, "
    "dress, skirt, pants, swimsuit, lingerie, textile, garment, "
    "text, watermark, deformed, blurry, bad anatomy"
)


async def _run_pipe_nsfw_subtract(job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
    """Pipeline NSFW por subtração: pessoa - rosto = área de roupa.

    1. Detectar PESSOA inteira → máscara de pessoa
    2. Subtrair ROSTO (top 35%) → máscara de roupa = pessoa - rosto
    3. SE8 NSFW inpaint APENAS na máscara de roupa
    4. Composite: NSFW no resultado, original em tudo mais
    5. Morfologia abertura/fechamento + bilateral nas bordas
    """
    import cv2 as _cv2
    import numpy as _np

    se10 = SE10Client()
    se8 = SE8Client()

    try:
        image_bytes = _decode_image(job.request.image)
        logger.info("Job %s: pipe_nsfw_subtract started", job.job_id)

        orig_img = _cv2.imdecode(_np.frombuffer(image_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if orig_img is None:
            raise ValueError("Failed to decode original image")
        orig_h, orig_w = orig_img.shape[:2]

        # === Stage 1: Detect person → full body mask ===
        job.update_stage("detecting", "processing", progress=10.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        t0 = time.time()
        person_seg = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}_person.jpg",
            classes="person, woman, man",
            box_threshold=0.20,
            text_threshold=0.15,
            mode="person",
        )
        seg_time = time.time() - t0

        if not person_seg.get("detected") or not person_seg.get("masks"):
            logger.warning("Job %s: no person detected", job.job_id)
            job.status = ClothesRemovalJobStatus.COMPLETED
            job.error = "No person detected"
            job.progress = 100.0
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        p_objects = person_seg.get("objects", [])
        p_masks = person_seg.get("masks", [])

        best_idx = 0
        best_area = 0
        for i, obj in enumerate(p_objects):
            if obj.get("area_pct", 0) > best_area:
                best_area = obj["area_pct"]
                best_idx = i

        logger.info("Job %s: person detected (area=%.1f%%) in %.1fs", job.job_id, best_area, seg_time)

        raw_p = _strip_data_uri(p_masks[best_idx])
        p_mask_bytes = base64.b64decode(_fix_b64_padding(raw_p))
        person_mask = _cv2.imdecode(_np.frombuffer(p_mask_bytes, _np.uint8), _cv2.IMREAD_GRAYSCALE)

        if person_mask is None:
            raise ValueError("Failed to decode person mask")
        if person_mask.shape[:2] != (orig_h, orig_w):
            person_mask = _cv2.resize(person_mask, (orig_w, orig_h))

        person_binary = (person_mask > 127).astype(_np.uint8) * 255

        # === Stage 2: Subtract face (top 45%) → clothing mask ===
        job.update_stage("detecting", "processing", progress=25.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        face_cutoff = int(orig_h * 0.45)
        face_region = _np.zeros_like(person_binary)
        face_region[:face_cutoff, :] = 255

        clothing_mask = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(face_region))

        clothing_pct = (clothing_mask > 0).sum() / clothing_mask.size * 100
        logger.info("Job %s: clothing mask = %.1f%% (person - face)", job.job_id, clothing_pct)

        if clothing_pct < 1.0:
            logger.warning("Job %s: clothing mask too small (%.1f%%)", job.job_id, clothing_pct)
            job.status = ClothesRemovalJobStatus.COMPLETED
            job.error = "No clothing area"
            job.progress = 100.0
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        # Mild dilation — small kernel to avoid face bleeding
        kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (7, 7))
        clothing_mask = _cv2.dilate(clothing_mask, kernel, iterations=1)

        # Feather edge — small blur to avoid face bleeding
        clothing_soft = clothing_mask.astype(_np.float32) / 255.0
        clothing_soft = _cv2.GaussianBlur(clothing_soft, (5, 5), 0)

        _, mask_buf = _cv2.imencode(".png", clothing_mask)
        nsfw_mask_b64 = _to_data_uri(base64.b64encode(mask_buf).decode("utf-8"), mime="image/png")

        # === Stage 3: SE8 NSFW 2-pass inpainting on clothing ONLY ===
        job.update_stage("inpainting", "processing", progress=35.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        nsfw_loras = [
            {"enabled": True, "model_name": "NsfwPovAllInOneLoraSdxl-000009.safetensors", "weight": 0.5},
            {"enabled": True, "model_name": "sd_xl_offset_example-lora_1.0.safetensors", "weight": 0.1},
            {"enabled": True, "model_name": "add-detail-xl.safetensors", "weight": 0.8},
            {"enabled": True, "model_name": "None", "weight": 1.0},
            {"enabled": True, "model_name": "None", "weight": 1.0},
        ]

        image_b64 = _to_data_uri(base64.b64encode(image_bytes).decode("utf-8"), mime="image/jpeg")

        # Pass 1: High denoise (0.75) — main removal
        t1 = time.time()
        result = await se8.inpaint(
            image_b64=image_b64,
            mask_b64=nsfw_mask_b64,
            prompt=NSFW_SUBTRACT_PROMPT,
            negative_prompt=NSFW_SUBTRACT_NEGATIVE,
            inpaint_strength=0.75,
            inpaint_respective_field=0.85,
            inpaint_erode_or_dilate=-8,
            loras=nsfw_loras,
            base_model="lustifySDXLNSFW_v20-inpainting.safetensors",
        )
        t1_time = time.time() - t1

        if not result or not result.get("base64"):
            logger.error("Job %s: SE8 pass 1 failed", job.job_id)
            job.status = ClothesRemovalJobStatus.FAILED
            job.error = "SE8 empty"
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        result1_bytes = base64.b64decode(result["base64"])
        logger.info("Job %s: pass 1 done in %.1fs", job.job_id, t1_time)

        # Pass 2: Low denoise (0.45) — refine remaining on same mask
        job.update_stage("inpainting", "processing", progress=50.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        result1_b64 = _to_data_uri(base64.b64encode(result1_bytes).decode("utf-8"), mime="image/png")

        t2 = time.time()
        result2 = await se8.inpaint(
            image_b64=result1_b64,
            mask_b64=nsfw_mask_b64,
            prompt=NSFW_SUBTRACT_PROMPT,
            negative_prompt=NSFW_SUBTRACT_NEGATIVE,
            inpaint_strength=0.45,
            inpaint_respective_field=0.90,
            inpaint_erode_or_dilate=-5,
            loras=nsfw_loras,
            base_model="lustifySDXLNSFW_v20-inpainting.safetensors",
        )
        t2_time = time.time() - t2

        result_bytes = result1_bytes  # Default to pass 1
        if result2 and result2.get("base64"):
            result_bytes = base64.b64decode(result2["base64"])
            logger.info("Job %s: pass 2 done in %.1fs", job.job_id, t2_time)
        else:
            logger.warning("Job %s: pass 2 failed, using pass 1", job.job_id)

        logger.info("Job %s: inpainting done (2 passes, total %.1fs)", job.job_id, t1_time + t2_time)

        result_img = _cv2.imdecode(_np.frombuffer(result_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if result_img is None:
            raise ValueError("Failed to decode result")
        if result_img.shape[:2] != (orig_h, orig_w):
            result_img = _cv2.resize(result_img, (orig_w, orig_h))

        # === Stage 4: Composite — NSFW in clothing mask, original elsewhere ===
        job.update_stage("inpainting", "processing", progress=65.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        soft_3ch = clothing_soft[:, :, _np.newaxis]
        composited = (result_img.astype(_np.float32) * soft_3ch +
                      orig_img.astype(_np.float32) * (1.0 - soft_3ch))
        composited = _np.clip(composited, 0, 255).astype(_np.uint8)

        # GUARANTEE: Force face region to exact original (no bleed from blur/dilation)
        composited[:face_cutoff, :] = orig_img[:face_cutoff, :]

        logger.info("Job %s: composite done (face region forced to original)", job.job_id)

        # === Stage 5: HSV Color Transfer — match inpainted area to surrounding skin ===
        job.update_stage("inpainting", "processing", progress=72.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        try:
            composited = _color_transfer(
                _cv2.imencode(".png", composited)[1].tobytes(),
                image_bytes,
                nsfw_mask_b64,
            )
            composited = _cv2.imdecode(_np.frombuffer(composited, _np.uint8), _cv2.IMREAD_COLOR)
            if composited is not None:
                composited[:face_cutoff, :] = orig_img[:face_cutoff, :]  # Re-ensure face
                logger.info("Job %s: HSV color transfer done", job.job_id)
        except Exception as e:
            logger.warning("Job %s: color transfer failed (%s)", job.job_id, e)

        # === Stage 6: Morphological operations on mask edges ===
        job.update_stage("inpainting", "processing", progress=80.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        kernel_open = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (3, 3))
        kernel_close = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))

        # Edge detection near clothing mask boundary
        edge_mask = _cv2.Canny(_cv2.cvtColor(composited, _cv2.COLOR_BGR2GRAY), 30, 100)
        edge_mask = _cv2.dilate(edge_mask, kernel_open, iterations=1)

        mask_near = _cv2.dilate((clothing_soft > 0.1).astype(_np.uint8), kernel_open, iterations=2)
        edge_region = (edge_mask > 0) & (mask_near > 0)

        if edge_region.any():
            for c in range(3):
                channel = composited[:, :, c].copy()
                channel = _cv2.morphologyEx(channel, _cv2.MORPH_OPEN, kernel_open)
                channel = _cv2.morphologyEx(channel, _cv2.MORPH_CLOSE, kernel_close)
                composited[:, :, c][edge_region] = channel[edge_region]

            smoothed = _cv2.bilateralFilter(composited, 5, 50, 50)
            composited[edge_region] = smoothed[edge_region]
            logger.info("Job %s: morphological blend done", job.job_id)

        # === Stage 6: Save ===
        job.update_stage("inpainting", "processing", progress=95.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        _, final_buf = _cv2.imencode(".png", composited)
        final_bytes = final_buf.tobytes()

        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)
        result_path = os.path.join(output_dir, f"{job.job_id}_result.png")
        with open(result_path, "wb") as f:
            f.write(final_bytes)

        job.result_path = result_path
        job.status = ClothesRemovalJobStatus.COMPLETED
        job.progress = 100.0
        job.objects_detected = 1
        job.update_stage("inpainting", "completed", progress=100.0)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))
        logger.info("Job %s: pipe_nsfw_subtract completed — %s", job.job_id, result_path)

    except Exception as e:
        logger.error("Job %s pipe_nsfw_subtract failed: %s", job.job_id, e, exc_info=True)
        job.status = ClothesRemovalJobStatus.FAILED
        job.error = str(e)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

    finally:
        await se10.close()
        await se8.close()


# =============================================================================
# Pipe NSFW 3-Layers: face+head+bg preserved, body isolated, clothes→NSFW
# =============================================================================

LAYER3_PROMPT = (
    "natural skin texture matching surrounding skin tone, realistic bare skin, "
    "seamless blend, photorealistic, soft lighting"
)

LAYER3_NEGATIVE = (
    "clothes, clothing, fabric, bra, straps, underwear, top, blouse, shirt, "
    "dress, skirt, pants, swimsuit, lingerie, textile, garment, "
    "text, watermark, deformed, blurry, bad anatomy"
)


async def _run_pipe_nsfw_3layers(job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
    """Pipeline NSFW 3-camadas:
    1. PRESERVAR: rosto+cabeça+cabelo+fundo (camada 1)
    2. ISOLAR: corpo = pessoa - rosto
    3. DETECTAR roupa DENTRO do corpo (Florence-2 AND body_mask)
    4. INPAINT NSFW na máscara efetiva (2-pass)
    5. COMPOR: original + resultado
    6. PÓS: HSV + morfologia + bilateral
    """
    import cv2 as _cv2
    import numpy as _np

    se10 = SE10Client()
    se8 = SE8Client()

    try:
        image_bytes = _decode_image(job.request.image)
        logger.info("Job %s: pipe_3layers started", job.job_id)

        orig_img = _cv2.imdecode(_np.frombuffer(image_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if orig_img is None:
            raise ValueError("Failed to decode original image")
        orig_h, orig_w = orig_img.shape[:2]

        # CAMADA 1: Detectar pessoa
        job.update_stage("detecting", "processing", progress=10.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        t0 = time.time()
        person_seg = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}_person.jpg",
            classes="person, woman, man",
            box_threshold=0.20,
            text_threshold=0.15,
            mode="person",
        )

        if not person_seg.get("detected") or not person_seg.get("masks"):
            logger.warning("Job %s: no person detected", job.job_id)
            job.status = ClothesRemovalJobStatus.COMPLETED
            job.error = "No person detected"
            job.progress = 100.0
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        p_objects = person_seg.get("objects", [])
        p_masks = person_seg.get("masks", [])
        best_idx = max(range(len(p_objects)), key=lambda i: p_objects[i].get("area_pct", 0))

        raw_p = _strip_data_uri(p_masks[best_idx])
        p_mask_bytes = base64.b64decode(_fix_b64_padding(raw_p))
        person_mask = _cv2.imdecode(_np.frombuffer(p_mask_bytes, _np.uint8), _cv2.IMREAD_GRAYSCALE)
        if person_mask is None:
            raise ValueError("Failed to decode person mask")
        if person_mask.shape[:2] != (orig_h, orig_w):
            person_mask = _cv2.resize(person_mask, (orig_w, orig_h))
        person_binary = (person_mask > 127).astype(_np.uint8) * 255
        logger.info("Job %s: person mask done in %.1fs", job.job_id, time.time() - t0)

        # CAMADA 2: Corpo = pessoa - rosto/cabeça
        job.update_stage("detecting", "processing", progress=25.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        contours, _ = _cv2.findContours(person_binary, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            raise ValueError("No contours in person mask")
        largest = max(contours, key=_cv2.contourArea)
        px, py, pw, ph = _cv2.boundingRect(largest)

        head_h = int(ph * 0.50)
        head_mask = _np.zeros_like(person_binary)
        head_mask[py:py + head_h, px:px + pw] = 255
        body_mask = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(head_mask))
        logger.info("Job %s: body mask = %.1f%%", job.job_id, (body_mask > 0).sum() / body_mask.size * 100)

        # CAMADA 3: Detectar roupa DENTRO do corpo
        job.update_stage("detecting", "processing", progress=35.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        clothes_seg = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}_clothes.jpg",
            classes="spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment",
            box_threshold=0.06,
            text_threshold=0.04,
            mode="clothes",
            detector="florence2",
        )

        effective_mask = _np.zeros((orig_h, orig_w), _np.uint8)

        if clothes_seg.get("detected") and clothes_seg.get("masks"):
            c_masks = clothes_seg.get("masks", [])
            clothes_combined = None
            for mask_b64 in c_masks:
                raw_c = _strip_data_uri(mask_b64)
                c_mask_bytes = base64.b64decode(_fix_b64_padding(raw_c))
                c_mask = _cv2.imdecode(_np.frombuffer(c_mask_bytes, _np.uint8), _cv2.IMREAD_GRAYSCALE)
                if c_mask is None:
                    continue
                if c_mask.shape[:2] != (orig_h, orig_w):
                    c_mask = _cv2.resize(c_mask, (orig_w, orig_h))
                c_binary = (c_mask > 127).astype(_np.uint8) * 255
                clothes_combined = c_binary if clothes_combined is None else _cv2.bitwise_or(clothes_combined, c_binary)

            if clothes_combined is not None:
                effective_mask = _cv2.bitwise_and(clothes_combined, body_mask)
                logger.info("Job %s: effective mask = %.1f%%", job.job_id, (effective_mask > 0).sum() / effective_mask.size * 100)

        effective_pct = (effective_mask > 0).sum() / effective_mask.size * 100
        if effective_pct < 0.5:
            logger.warning("Job %s: no clothing in body (%.1f%%)", job.job_id, effective_pct)
            job.status = ClothesRemovalJobStatus.COMPLETED
            job.error = "No clothing in body"
            job.progress = 100.0
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        # Dilate + feather
        kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (7, 7))
        effective_mask = _cv2.dilate(effective_mask, kernel, iterations=1)
        effective_soft = _cv2.GaussianBlur(effective_mask.astype(_np.float32) / 255.0, (5, 5), 0)

        _, eff_buf = _cv2.imencode(".png", effective_mask)
        eff_mask_b64 = _to_data_uri(base64.b64encode(eff_buf).decode("utf-8"), mime="image/png")

        # INPAINT: 2-pass with same effective mask
        job.update_stage("inpainting", "processing", progress=45.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        nsfw_loras = [
            {"enabled": True, "model_name": "NsfwPovAllInOneLoraSdxl-000009.safetensors", "weight": 0.5},
            {"enabled": True, "model_name": "sd_xl_offset_example-lora_1.0.safetensors", "weight": 0.1},
            {"enabled": True, "model_name": "add-detail-xl.safetensors", "weight": 0.8},
            {"enabled": True, "model_name": "None", "weight": 1.0},
            {"enabled": True, "model_name": "None", "weight": 1.0},
        ]

        image_b64 = _to_data_uri(base64.b64encode(image_bytes).decode("utf-8"), mime="image/jpeg")

        # Pass 1: 0.75 denoise
        result1 = await se8.inpaint(
            image_b64=image_b64, mask_b64=eff_mask_b64,
            prompt=LAYER3_PROMPT, negative_prompt=LAYER3_NEGATIVE,
            inpaint_strength=0.75, inpaint_respective_field=0.85,
            inpaint_erode_or_dilate=-8, loras=nsfw_loras,
            base_model="lustifySDXLNSFW_v20-inpainting.safetensors",
        )
        if not result1 or not result1.get("base64"):
            logger.error("Job %s: SE8 pass 1 failed", job.job_id)
            job.status = ClothesRemovalJobStatus.FAILED
            job.error = "SE8 empty"
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return
        r1_bytes = base64.b64decode(result1["base64"])

        # Pass 2: 0.45 denoise
        job.update_stage("inpainting", "processing", progress=60.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        r1_b64 = _to_data_uri(base64.b64encode(r1_bytes).decode("utf-8"), mime="image/png")
        result2 = await se8.inpaint(
            image_b64=r1_b64, mask_b64=eff_mask_b64,
            prompt=LAYER3_PROMPT, negative_prompt=LAYER3_NEGATIVE,
            inpaint_strength=0.45, inpaint_respective_field=0.90,
            inpaint_erode_or_dilate=-5, loras=nsfw_loras,
            base_model="lustifySDXLNSFW_v20-inpainting.safetensors",
        )

        inpainted_bytes = r1_bytes
        if result2 and result2.get("base64"):
            inpainted_bytes = base64.b64decode(result2["base64"])

        inpainted_img = _cv2.imdecode(_np.frombuffer(inpainted_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if inpainted_img is not None and inpainted_img.shape[:2] != (orig_h, orig_w):
            inpainted_img = _cv2.resize(inpainted_img, (orig_w, orig_h))

        # COMPOSIÇÃO: original + inpainted
        job.update_stage("inpainting", "processing", progress=75.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        soft_3ch = effective_soft[:, :, _np.newaxis]
        composited = (inpainted_img.astype(_np.float32) * soft_3ch +
                      orig_img.astype(_np.float32) * (1.0 - soft_3ch))
        composited = _np.clip(composited, 0, 255).astype(_np.uint8)

        # FORCE: head+face = exact original
        composited[head_mask > 0] = orig_img[head_mask > 0]

        # HSV color transfer
        try:
            comp_bytes = _cv2.imencode(".png", composited)[1].tobytes()
            corrected = _color_transfer(comp_bytes, image_bytes, eff_mask_b64)
            corrected_img = _cv2.imdecode(_np.frombuffer(corrected, _np.uint8), _cv2.IMREAD_COLOR)
            if corrected_img is not None and corrected_img.shape[:2] == (orig_h, orig_w):
                composited = corrected_img
                composited[head_mask > 0] = orig_img[head_mask > 0]
        except Exception as e:
            logger.warning("Job %s: color transfer failed (%s)", job.job_id, e)

        # Morphological blend on edges
        job.update_stage("inpainting", "processing", progress=85.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        kernel_open = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (3, 3))
        kernel_close = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))
        edge_mask = _cv2.Canny(_cv2.cvtColor(composited, _cv2.COLOR_BGR2GRAY), 30, 100)
        edge_mask = _cv2.dilate(edge_mask, kernel_open, iterations=1)
        mask_near = _cv2.dilate((effective_soft > 0.1).astype(_np.uint8), kernel_open, iterations=2)
        edge_region = (edge_mask > 0) & (mask_near > 0)

        if edge_region.any():
            for c in range(3):
                ch = composited[:, :, c].copy()
                ch = _cv2.morphologyEx(ch, _cv2.MORPH_OPEN, kernel_open)
                ch = _cv2.morphologyEx(ch, _cv2.MORPH_CLOSE, kernel_close)
                composited[:, :, c][edge_region] = ch[edge_region]
            smoothed = _cv2.bilateralFilter(composited, 5, 50, 50)
            composited[edge_region] = smoothed[edge_region]

        # SAVE
        job.update_stage("inpainting", "processing", progress=95.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        _, final_buf = _cv2.imencode(".png", composited)
        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)
        result_path = os.path.join(output_dir, f"{job.job_id}_result.png")
        with open(result_path, "wb") as f:
            f.write(final_buf.tobytes())

        job.result_path = result_path
        job.status = ClothesRemovalJobStatus.COMPLETED
        job.progress = 100.0
        job.objects_detected = len(c_masks) if clothes_seg.get("detected") else 0
        job.update_stage("inpainting", "completed", progress=100.0)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))
        logger.info("Job %s: pipe_3layers completed — %s", job.job_id, result_path)

    except Exception as e:
        logger.error("Job %s pipe_3layers failed: %s", job.job_id, e, exc_info=True)
        job.status = ClothesRemovalJobStatus.FAILED
        job.error = str(e)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

    finally:
        await se10.close()
        await se8.close()


# =============================================================================
# Pipe NSFW 3-Layers MAX: 3-layer detection + full body inpaint (max removal)
# =============================================================================

async def _run_pipe_nsfw_3layers_max(job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
    """Combina pipe_3layers (precisão) + pipe_nsfw_subtract (remoção máxima):
    1. Pessoa → head(50%) = body (rosto+cabeça PRESERVADOS)
    2. INPAINT corpo INTEIRO (não só roupa)
    3. Composite: original (rosto+cabeça+fundo) + corpo NSFW
    """
    import cv2 as _cv2
    import numpy as _np

    se10 = SE10Client()
    se8 = SE8Client()

    try:
        image_bytes = _decode_image(job.request.image)
        logger.info("Job %s: pipe_3layers_max started", job.job_id)

        orig_img = _cv2.imdecode(_np.frombuffer(image_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if orig_img is None:
            raise ValueError("Failed to decode")
        orig_h, orig_w = orig_img.shape[:2]

        # CAMADA 1: Pessoa
        job.update_stage("detecting", "processing", progress=10.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        person_seg = await se10.segment(
            image_bytes=image_bytes, filename=f"{job.job_id}_person.jpg",
            classes="person, woman, man", box_threshold=0.20, text_threshold=0.15, mode="person",
        )
        if not person_seg.get("detected") or not person_seg.get("masks"):
            job.status = ClothesRemovalJobStatus.COMPLETED
            job.error = "No person detected"
            job.progress = 100.0
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        best_idx = max(range(len(person_seg["objects"])), key=lambda i: person_seg["objects"][i].get("area_pct", 0))
        raw_p = _strip_data_uri(person_seg["masks"][best_idx])
        person_mask = _cv2.imdecode(
            _np.frombuffer(base64.b64decode(_fix_b64_padding(raw_p)), _np.uint8), _cv2.IMREAD_GRAYSCALE)
        if person_mask is None:
            raise ValueError("Bad person mask")
        if person_mask.shape[:2] != (orig_h, orig_w):
            person_mask = _cv2.resize(person_mask, (orig_w, orig_h))
        person_binary = (person_mask > 127).astype(_np.uint8) * 255

        # CAMADA 2: Body = person - head
        # Head: top 40% of person mask bbox (includes hair via mask shape)
        job.update_stage("detecting", "processing", progress=25.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        contours, _ = _cv2.findContours(person_binary, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            raise ValueError("No contours")
        largest = max(contours, key=_cv2.contourArea)
        px, py, pw, ph = _cv2.boundingRect(largest)

        head_h = int(ph * 0.40)
        # Head mask: follow the person mask silhouette (not just bbox rectangle)
        # This captures hair that extends beyond the head bbox
        head_mask = _np.zeros_like(person_binary)
        head_mask[py:py + head_h, px:px + pw] = 255
        head_mask = _cv2.bitwise_and(head_mask, person_binary)  # clip to person shape
        # Add padding around head for hair edge detection
        head_mask = _cv2.dilate(head_mask, _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (15, 15)), iterations=2)
        head_mask = _cv2.bitwise_and(head_mask, person_binary)  # keep only within person

        body_mask = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(head_mask))
        body_pct = (body_mask > 0).sum() / body_mask.size * 100
        logger.info("Job %s: body = %.1f%% (head = top %.0f%% of bbox)", job.job_id, body_pct, 40.0)

        # ====================================================================
        # SKIN COLOR REFERENCE: detect exposed skin for color matching
        # ====================================================================
        # Detect clothing to find exposed skin (body NOT covered by clothes)
        clothes_seg = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}_clothes_ref.jpg",
            classes="spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment",
            box_threshold=0.06, text_threshold=0.04,
            mode="clothes", detector="florence2",
        )

        clothes_combined = None
        if clothes_seg.get("detected") and clothes_seg.get("masks"):
            for mb in clothes_seg.get("masks", []):
                raw_c = _strip_data_uri(mb)
                c_bytes = base64.b64decode(_fix_b64_padding(raw_c))
                cm = _cv2.imdecode(_np.frombuffer(c_bytes, _np.uint8), _cv2.IMREAD_GRAYSCALE)
                if cm is not None:
                    if cm.shape[:2] != (orig_h, orig_w):
                        cm = _cv2.resize(cm, (orig_w, orig_h))
                    cb = (cm > 127).astype(_np.uint8) * 255
                    clothes_combined = cb if clothes_combined is None else _cv2.bitwise_or(clothes_combined, cb)

        # Exposed skin = body AND NOT clothes (where skin is visible)
        if clothes_combined is not None:
            exposed_skin = _cv2.bitwise_and(body_mask, _cv2.bitwise_not(clothes_combined))
        else:
            exposed_skin = body_mask  # If no clothes detected, all body is exposed

        exposed_pct = (exposed_skin > 0).sum() / exposed_skin.size * 100
        logger.info("Job %s: exposed skin = %.1f%%", job.job_id, exposed_pct)

        # Extract median HSV from exposed skin
        orig_hsv = _cv2.cvtColor(orig_img, _cv2.COLOR_BGR2HSV)
        if (exposed_skin > 0).any():
            skin_pixels = orig_hsv[exposed_skin > 0]
            median_h = float(_np.median(skin_pixels[:, 0]))
            median_s = float(_np.median(skin_pixels[:, 1]))
            median_v = float(_np.median(skin_pixels[:, 2]))
            logger.info("Job %s: skin reference — H=%.0f S=%.0f V=%.0f", job.job_id, median_h, median_s, median_v)
        else:
            median_h, median_s, median_v = 100.0, 50.0, 200.0  # fallback
            logger.info("Job %s: no exposed skin, using default", job.job_id)

        # ====================================================================
        # INPAINT: body_mask (torso inteiro para NSFW)
        # ====================================================================
        clothing_exact = _cv2.bitwise_and(body_mask, _cv2.bitwise_not(exposed_skin))
        clothing_pct = (clothing_exact > 0).sum() / clothing_exact.size * 100
        logger.info("Job %s: clothing exact = %.1f%% (body was %.1f%%)", job.job_id, clothing_pct, body_pct)

        job.update_stage("inpainting", "processing", progress=35.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        # v15: use body_mask (not clothing_exact) for wider inpaint area
        kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (16, 16))
        inpaint_mask = _cv2.dilate(body_mask, kernel, iterations=2)
        inpaint_soft = _cv2.GaussianBlur(inpaint_mask.astype(_np.float32) / 255.0, (5, 5), 0)

        _, mask_buf = _cv2.imencode(".png", inpaint_mask)
        mask_b64 = _to_data_uri(base64.b64encode(mask_buf).decode("utf-8"), mime="image/png")

        nsfw_loras = [
            {"enabled": True, "model_name": "NsfwPovAllInOneLoraSdxl-000009.safetensors", "weight": 0.2},
            {"enabled": True, "model_name": "sd_xl_offset_example-lora_1.0.safetensors", "weight": 0.1},
            {"enabled": True, "model_name": "add-detail-xl.safetensors", "weight": 0.8},
            {"enabled": True, "model_name": "None", "weight": 1.0},
            {"enabled": True, "model_name": "None", "weight": 1.0},
        ]

        image_b64 = _to_data_uri(base64.b64encode(image_bytes).decode("utf-8"), mime="image/jpeg")

        # v14: MERGE — original simple params + new exact mask
        # Reverted from job cr_f5a80bef266e that generated real NSFW

        # Pass 1: single pass with proven params
        result1 = await se8.inpaint(
            image_b64=image_b64, mask_b64=mask_b64,
            prompt=DEFAULT_CLOTHES_PROMPT,
            negative_prompt=DEFAULT_CLOTHES_NEGATIVE,
            inpaint_strength=0.75, inpaint_respective_field=0.85,
            inpaint_erode_or_dilate=-8, loras=nsfw_loras,
            base_model="juggernautXL_v8Rundiffusion.safetensors",
        )
        if not result1 or not result1.get("base64"):
            job.status = ClothesRemovalJobStatus.FAILED
            job.error = "SE8 empty"
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return
        inpainted_bytes = base64.b64decode(result1["base64"])

        inpainted_img = _cv2.imdecode(_np.frombuffer(inpainted_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if inpainted_img is not None and inpainted_img.shape[:2] != (orig_h, orig_w):
            inpainted_img = _cv2.resize(inpainted_img, (orig_w, orig_h))

        # COMPOSIÇÃO
        job.update_stage("inpainting", "processing", progress=75.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        composited = (inpainted_img.astype(_np.float32) * inpaint_soft[:, :, None] +
                      orig_img.astype(_np.float32) * (1.0 - inpaint_soft[:, :, None]))
        composited = _np.clip(composited, 0, 255).astype(_np.uint8)
        composited[head_mask > 0] = orig_img[head_mask > 0]

        # Color transfer with exposed_skin reference
        try:
            comp_bytes = _cv2.imencode(".png", composited)[1].tobytes()
            corrected = _color_transfer(comp_bytes, image_bytes, mask_b64, reference_mask=exposed_skin)
            corrected_img = _cv2.imdecode(_np.frombuffer(corrected, _np.uint8), _cv2.IMREAD_COLOR)
            if corrected_img is not None and corrected_img.shape[:2] == (orig_h, orig_w):
                composited = corrected_img
                composited[head_mask > 0] = orig_img[head_mask > 0]
        except Exception:
            pass

        job.update_stage("inpainting", "processing", progress=85.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        # Edge blend — original params
        ko = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (3, 3))
        kc = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))
        em = _cv2.Canny(_cv2.cvtColor(composited, _cv2.COLOR_BGR2GRAY), 30, 100)
        em = _cv2.dilate(em, ko, iterations=1)
        mn = _cv2.dilate((inpaint_soft > 0.1).astype(_np.uint8), ko, iterations=2)
        er = (em > 0) & (mn > 0)
        if er.any():
            for c in range(3):
                ch = composited[:, :, c].copy()
                ch = _cv2.morphologyEx(ch, _cv2.MORPH_OPEN, ko)
                ch = _cv2.morphologyEx(ch, _cv2.MORPH_CLOSE, kc)
                composited[:, :, c][er] = ch[er]
            composited[er] = _cv2.bilateralFilter(composited, 5, 50, 50)[er]

        # SAVE
        job.update_stage("inpainting", "processing", progress=95.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        _, fb = _cv2.imencode(".png", composited)
        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)

        # Save debug masks — numbered in pipeline sequence (0→final)
        try:
            exposed_vis = exposed_skin if exposed_skin is not None else _np.zeros_like(person_binary)

            def _save_mask(num: int, name: str, mask) -> None:
                tag = f"{num:02d}_{name}"
                if mask.ndim == 2:
                    _cv2.imwrite(os.path.join(output_dir, f"{tag}.png"), mask)
                else:
                    _cv2.imwrite(os.path.join(output_dir, f"{tag}.png"), mask)

            # Step-by-step pipeline sequence
            _save_mask(0, "original", orig_img)                # 00: entrada
            _save_mask(1, "person", person_binary)              # 01: detecção SE10
            _save_mask(2, "head_protected", head_mask)          # 02: cabeça (protegida)
            _save_mask(3, "body", body_mask)                    # 03: corpo = pessoa - cabeça
            _save_mask(4, "exposed_skin", exposed_vis)          # 04: pele exposta (ref cor)
            _save_mask(5, "clothing", clothing_exact)           # 05: ROUPA EXATA (inverso pele)
            _save_mask(6, "inpaint_mask", inpaint_mask)         # 06: dilatado → NSFW
            _save_mask(7, "result", composited)                 # 07: resultado final

            # Overlay com cores e números
            overlay = orig_img.copy()
            h_ov = overlay.copy(); h_ov[head_mask > 0] = [0, 0, 255]
            overlay = _cv2.addWeighted(overlay, 0.4, h_ov, 0.6, 0)
            e_ov = overlay.copy(); e_ov[exposed_vis > 0] = [0, 255, 0]
            overlay = _cv2.addWeighted(overlay, 0.4, e_ov, 0.6, 0)
            c_ov = overlay.copy(); c_ov[clothing_exact > 0] = [255, 0, 255]
            overlay = _cv2.addWeighted(overlay, 0.4, c_ov, 0.6, 0)
            i_ov = overlay.copy(); i_ov[inpaint_mask > 0] = [0, 255, 255]
            overlay = _cv2.addWeighted(overlay, 0.4, i_ov, 0.6, 0)

            _cv2.putText(overlay, "1=HEAD 4=SKIN 5=CLOTH 6=INPAINT",
                         (10, 30), _cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            _cv2.imwrite(os.path.join(output_dir, f"{job.job_id}_mask_overlay.png"), overlay)

            logger.info("Job %s: 8 sequential masks saved (00-07)", job.job_id)
        except Exception as e:
            logger.warning("Job %s: debug failed (%s)", job.job_id, e)

        result_path = os.path.join(output_dir, f"{job.job_id}_result.png")
        with open(result_path, "wb") as f:
            f.write(fb.tobytes())

        job.result_path = result_path
        job.status = ClothesRemovalJobStatus.COMPLETED
        job.progress = 100.0
        job.objects_detected = 1
        job.update_stage("inpainting", "completed", progress=100.0)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))
        logger.info("Job %s: pipe_3layers_max completed — %s", job.job_id, result_path)

    except Exception as e:
        logger.error("Job %s pipe_3layers_max failed: %s", job.job_id, e, exc_info=True)
        job.status = ClothesRemovalJobStatus.FAILED
        job.error = str(e)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

    finally:
        await se10.close()
        await se8.close()


async def _run_nsfw_test(job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
    """TEST pipeline — clothing_exact + 7% expansion + head_mask + Reinhard LAB + collage.

    clothing_exact = body AND NOT exposed_skin.
    7% adaptive dilation expands clothing to catch strap edges.
    head_mask (40%) protects face — NOT face_only.
    """
    import cv2 as _cv2
    import numpy as _np

    se10 = SE10Client()
    se8 = SE8Client()

    try:
        image_bytes = _decode_image(job.request.image)
        logger.info("Job %s: nsfw_test (PLAN-1) started", job.job_id)

        orig_img = _cv2.imdecode(_np.frombuffer(image_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if orig_img is None:
            raise ValueError("Failed to decode")
        orig_h, orig_w = orig_img.shape[:2]

        job.update_stage("detecting", "processing", progress=10.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        person_seg = await se10.segment(
            image_bytes=image_bytes, filename=f"{job.job_id}_person.jpg",
            classes="person, woman, man", box_threshold=0.20, text_threshold=0.15, mode="person",
        )
        if not person_seg.get("detected") or not person_seg.get("masks"):
            job.status = ClothesRemovalJobStatus.COMPLETED
            job.error = "No person detected"
            job.progress = 100.0
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        best_idx = max(range(len(person_seg["objects"])), key=lambda i: person_seg["objects"][i].get("area_pct", 0))
        raw_p = _strip_data_uri(person_seg["masks"][best_idx])
        person_mask = _cv2.imdecode(
            _np.frombuffer(base64.b64decode(_fix_b64_padding(raw_p)), _np.uint8), _cv2.IMREAD_GRAYSCALE)
        if person_mask is None:
            raise ValueError("Bad person mask")
        if person_mask.shape[:2] != (orig_h, orig_w):
            person_mask = _cv2.resize(person_mask, (orig_w, orig_h))
        person_binary = (person_mask > 127).astype(_np.uint8) * 255

        job.update_stage("detecting", "processing", progress=25.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        contours, _ = _cv2.findContours(person_binary, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            raise ValueError("No contours")
        largest = max(contours, key=_cv2.contourArea)
        px, py, pw, ph = _cv2.boundingRect(largest)

        head_h = int(ph * 0.40)
        head_mask = _np.zeros_like(person_binary)
        head_mask[py:py + head_h, px:px + pw] = 255
        head_mask = _cv2.bitwise_and(head_mask, person_binary)
        head_mask = _cv2.dilate(head_mask, _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (15, 15)), iterations=2)
        head_mask = _cv2.bitwise_and(head_mask, person_binary)

        body_mask = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(head_mask))

        clothes_seg = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}_clothes_ref.jpg",
            classes="spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment",
            box_threshold=0.06, text_threshold=0.04,
            mode="clothes", detector="florence2",
        )

        clothes_combined = None
        if clothes_seg.get("detected") and clothes_seg.get("masks"):
            for mb in clothes_seg.get("masks", []):
                raw_c = _strip_data_uri(mb)
                c_bytes = base64.b64decode(_fix_b64_padding(raw_c))
                cm = _cv2.imdecode(_np.frombuffer(c_bytes, _np.uint8), _cv2.IMREAD_GRAYSCALE)
                if cm is not None:
                    if cm.shape[:2] != (orig_h, orig_w):
                        cm = _cv2.resize(cm, (orig_w, orig_h))
                    cb = (cm > 127).astype(_np.uint8) * 255
                    clothes_combined = cb if clothes_combined is None else _cv2.bitwise_or(clothes_combined, cb)

        if clothes_combined is not None:
            exposed_skin = _cv2.bitwise_and(body_mask, _cv2.bitwise_not(clothes_combined))
        else:
            exposed_skin = body_mask

        # Clothing = body AND NOT exposed_skin
        clothing_exact = _cv2.bitwise_and(body_mask, _cv2.bitwise_not(exposed_skin))

        # Step 1: CLOSE all holes in clothing — aggressive multi-pass
        # Pass 1: medium kernel fills small gaps
        ck1 = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (15, 15))
        clothing_closed = _cv2.morphologyEx(clothing_exact, _cv2.MORPH_CLOSE, ck1, iterations=4)
        # Pass 2: large kernel fills remaining gaps
        ck2 = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (25, 25))
        clothing_closed = _cv2.morphologyEx(clothing_closed, _cv2.MORPH_CLOSE, ck2, iterations=3)
        # Pass 3: fill from inside using floodFill
        flood = clothing_closed.copy()
        flood_mask = _np.zeros((flood.shape[0] + 2, flood.shape[1] + 2), _np.uint8)
        # Find center of clothing mass
        cts_f, _ = _cv2.findContours(clothing_closed, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
        if cts_f:
            M = _cv2.moments(max(cts_f, key=_cv2.contourArea))
            if M["m00"] > 0:
                cx, cy = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
                _cv2.floodFill(flood, flood_mask, (cx, cy), 255)
                clothing_closed = _cv2.bitwise_or(clothing_closed, flood)

        # Adaptive dilation: 3% — subtle edge expansion
        contours_c, _ = _cv2.findContours(clothing_closed, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
        if contours_c:
            all_pts = _np.vstack(contours_c)
            _, _, cw, ch = _cv2.boundingRect(all_pts)
            dilation_px = max(3, int(min(cw, ch) * 0.03))
        else:
            dilation_px = 5
        expand_kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (dilation_px, dilation_px))
        clothes_expanded = _cv2.dilate(clothing_closed, expand_kernel, iterations=2)

        # head_adjusted: subtract expanded clothing from head (update ONLY the head)
        head_adjusted = _cv2.bitwise_and(head_mask, _cv2.bitwise_not(clothes_expanded))

        # inpaint_mask = clothes_expanded BINARY — goes to SE8 UNTOUCHED
        inpaint_mask = clothes_expanded

        clothes_pct = (clothing_exact > 0).sum() / clothing_exact.size * 100
        head_orig_pct = _cv2.countNonZero(head_mask) / head_mask.size * 100
        head_adj_pct = _cv2.countNonZero(head_adjusted) / head_adjusted.size * 100
        logger.info("Job %s: clothes=%.1f%% dil=%dpx head_orig=%.1f%% head_adj=%.1f%%",
                     job.job_id, clothes_pct, dilation_px, head_orig_pct, head_adj_pct)

        job.update_stage("inpainting", "processing", progress=35.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        _, mask_buf = _cv2.imencode(".png", inpaint_mask)
        mask_b64 = _to_data_uri(base64.b64encode(mask_buf).decode("utf-8"), mime="image/png")

        nsfw_loras = [
            {"enabled": True, "model_name": "NsfwPovAllInOneLoraSdxl-000009.safetensors", "weight": 0.2},
            {"enabled": True, "model_name": "sd_xl_offset_example-lora_1.0.safetensors", "weight": 0.1},
            {"enabled": True, "model_name": "add-detail-xl.safetensors", "weight": 0.8},
            {"enabled": True, "model_name": "None", "weight": 1.0},
            {"enabled": True, "model_name": "None", "weight": 1.0},
        ]

        image_b64 = _to_data_uri(base64.b64encode(image_bytes).decode("utf-8"), mime="image/jpeg")

        # Pass 1: single pass — proven params
        result1 = await se8.inpaint(
            image_b64=image_b64, mask_b64=mask_b64,
            prompt=DEFAULT_CLOTHES_PROMPT,
            negative_prompt=DEFAULT_CLOTHES_NEGATIVE,
            inpaint_strength=0.75, inpaint_respective_field=0.85,
            inpaint_erode_or_dilate=-8, loras=nsfw_loras,
            base_model="juggernautXL_v8Rundiffusion.safetensors",
        )
        if not result1 or not result1.get("base64"):
            job.status = ClothesRemovalJobStatus.FAILED
            job.error = "SE8 empty"
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return
        inpainted_bytes = base64.b64decode(result1["base64"])

        inpainted_img = _cv2.imdecode(_np.frombuffer(inpainted_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if inpainted_img is not None and inpainted_img.shape[:2] != (orig_h, orig_w):
            inpainted_img = _cv2.resize(inpainted_img, (orig_w, orig_h))

        job.update_stage("inpainting", "processing", progress=75.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        # Force head_adjusted = original (not head_mask — expanded clothing excluded)
        inpainted_img[head_adjusted > 0] = orig_img[head_adjusted > 0]

        # STAGE 1: Reinhard Color Transfer (LAB space)
        try:
            src_lab = _cv2.cvtColor(inpainted_img, _cv2.COLOR_BGR2LAB).astype(_np.float32)
            ref_lab = _cv2.cvtColor(orig_img, _cv2.COLOR_BGR2LAB).astype(_np.float32)
            src_region = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(head_adjusted))

            for ch in range(3):
                src_pixels = src_lab[:, :, ch][src_region > 0] if (src_region > 0).any() else src_lab[:, :, ch].ravel()
                ref_pixels = ref_lab[:, :, ch][exposed_skin > 0] if (exposed_skin > 0).any() else ref_lab[:, :, ch].ravel()
                src_m, src_s = float(src_pixels.mean()), float(src_pixels.std())
                ref_m, ref_s = float(ref_pixels.mean()), float(ref_pixels.std())
                if src_s > 1e-6:
                    src_lab[:, :, ch] = (src_lab[:, :, ch] - src_m) * (ref_s / src_s) + ref_m

            color_corrected = _cv2.cvtColor(_np.clip(src_lab, 0, 255).astype(_np.uint8), _cv2.COLOR_LAB2BGR)
            color_corrected[head_adjusted > 0] = orig_img[head_adjusted > 0]
            logger.info("Job %s: Reinhard LAB applied", job.job_id)
        except Exception as e:
            logger.warning("Job %s: Reinhard LAB failed (%s), using inpainted", job.job_id, e)
            color_corrected = inpainted_img

        # STAGE 2: GaussianBlur collage
        person_soft = _cv2.GaussianBlur(person_binary.astype(_np.float32) / 255.0, (31, 31), 0)
        person_soft = _cv2.GaussianBlur(person_soft, (15, 15), 0)
        composited = (color_corrected.astype(_np.float32) * person_soft[:, :, None] +
                      orig_img.astype(_np.float32) * (1.0 - person_soft[:, :, None]))
        composited = _np.clip(composited, 0, 255).astype(_np.uint8)

        # Head_adjusted protection (expanded clothing NOT protected)
        composited[head_adjusted > 0] = orig_img[head_adjusted > 0]
        logger.info("Job %s: collage + LAB applied", job.job_id)

        job.update_stage("inpainting", "processing", progress=90.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        _, fb = _cv2.imencode(".png", composited)
        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)

        try:
            def _save_mask(num: int, name: str, mask) -> None:
                tag = f"{num:02d}_{name}"
                _cv2.imwrite(os.path.join(output_dir, f"{tag}.png"), mask)

            _save_mask(0, "original", orig_img)
            _save_mask(1, "person", person_binary)
            _save_mask(2, "head_original", head_mask)
            _save_mask(3, "head_adjusted", head_adjusted)
            _save_mask(4, "body", body_mask)
            _save_mask(5, "clothing_closed", clothing_closed)
            _save_mask(6, "clothing_expanded", clothes_expanded)
            _save_mask(7, "inpaint_mask", inpaint_mask)
            _save_mask(8, "result", composited)

            overlay = orig_img.copy()
            h_ov = overlay.copy(); h_ov[head_adjusted > 0] = [0, 0, 255]  # RED = head adjusted
            overlay = _cv2.addWeighted(overlay, 0.4, h_ov, 0.6, 0)
            c_ov = overlay.copy(); c_ov[clothes_expanded > 0] = [255, 0, 255]  # MAGENTA = expanded clothes
            overlay = _cv2.addWeighted(overlay, 0.4, c_ov, 0.6, 0)
            i_ov = overlay.copy(); i_ov[inpaint_mask > 0] = [0, 255, 255]  # YELLOW = inpaint
            overlay = _cv2.addWeighted(overlay, 0.4, i_ov, 0.6, 0)

            # Show difference between head_original and head_adjusted in WHITE
            head_diff = _cv2.bitwise_and(head_mask, _cv2.bitwise_not(head_adjusted))
            d_ov = overlay.copy(); d_ov[head_diff > 0] = [255, 255, 255]  # WHITE = subtracted from head
            overlay = _cv2.addWeighted(overlay, 0.6, d_ov, 0.4, 0)

            _cv2.putText(overlay, "RED=head_adjusted MAGENTA=clothes YELLOW=inpaint WHITE=subtracted",
                         (10, 30), _cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            _cv2.imwrite(os.path.join(output_dir, f"{job.job_id}_mask_overlay.png"), overlay)
        except Exception as e:
            import traceback
            logger.warning("Job %s: debug failed (%s)\n%s", job.job_id, e, traceback.format_exc())

        result_path = os.path.join(output_dir, f"{job.job_id}_result.png")
        with open(result_path, "wb") as f:
            f.write(fb.tobytes())

        job.result_path = result_path
        job.status = ClothesRemovalJobStatus.COMPLETED
        job.progress = 100.0
        job.objects_detected = 1
        job.update_stage("inpainting", "completed", progress=100.0)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))
        logger.info("Job %s: nsfw_test completed — %s", job.job_id, result_path)

    except Exception as e:
        logger.error("Job %s nsfw_test failed: %s", job.job_id, e, exc_info=True)
        job.status = ClothesRemovalJobStatus.FAILED
        job.error = str(e)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

    finally:
        await se10.close()
        await se8.close()
