"""Pipeline for SE11 Clothes Removal — slim dispatcher.

Routes to independent pipeline files:
  - mode="nsfw" → pipeline_nsfw.py (production: retry + pose validation)
  - mode="nsfw_test" → pipeline_nsfw_experimental.py (test: debug, no retry)
  - mode="progressive" → inline (4-pass progressive)
  - mode="clothes"/"person" → inline (single-pass)
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import time

from common.log_utils import get_logger
from common.datetime_utils import now_brazil

from app.core.config import settings
from app.core.models import ClothesRemovalJob, ClothesRemovalJobStatus
from app.infrastructure.http_client import SE10Client, SE8Client
from app.infrastructure.redis_store import ClothesRemovalJobStore
from app.services.head_detector import detect_head_mask

logger = get_logger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

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

# ─── Helper Functions ────────────────────────────────────────────────────────

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
    decoded = []
    for m in masks:
        raw = _strip_data_uri(m)
        arr = np.frombuffer(base64.b64decode(_fix_b64_padding(raw)), np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            decoded.append(img)
    if not decoded:
        return ""
    ref = decoded[0]
    combined = np.zeros_like(ref)
    for img in decoded:
        if img.shape == ref.shape:
            combined = cv2.bitwise_or(combined, img)
    _, buf = cv2.imencode(".png", combined)
    return _to_data_uri(base64.b64encode(buf).decode("utf-8"), mime="image/png")


def dilate_mask(mask_uri: str, kernel_size: int = 21, iterations: int = 2) -> str:
    import cv2
    import numpy as np
    raw = _strip_data_uri(mask_uri)
    arr = np.frombuffer(base64.b64decode(_fix_b64_padding(raw)), np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return mask_uri
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    dilated = cv2.dilate(img, kernel, iterations=iterations)
    _, buf = cv2.imencode(".png", dilated)
    return _to_data_uri(base64.b64encode(buf).decode("utf-8"), mime="image/png")


def _erode_mask(mask_uri: str, kernel_size: int = 15, iterations: int = 2) -> str:
    import cv2
    import numpy as np
    raw = _strip_data_uri(mask_uri)
    arr = np.frombuffer(base64.b64decode(_fix_b64_padding(raw)), np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return mask_uri
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    eroded = cv2.erode(img, kernel, iterations=iterations)
    _, buf = cv2.imencode(".png", eroded)
    return _to_data_uri(base64.b64encode(buf).decode("utf-8"), mime="image/png")


def _keep_object(obj: dict, image_height: int) -> bool:
    area = obj.get("area_pct", 0)
    bbox = obj.get("bbox", [0, 0, 0, 0])
    if len(bbox) == 4:
        _, y, _, h = bbox
        if y + h > image_height * 0.95 and area < 1.0:
            return False
    if area < 0.1:
        return False
    return True


def _color_transfer(result_bytes: bytes, original_bytes: bytes, mask_uri: str) -> bytes:
    import cv2
    import numpy as np
    raw = _strip_data_uri(mask_uri)
    arr = np.frombuffer(base64.b64decode(_fix_b64_padding(raw)), np.uint8)
    mask = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return result_bytes
    result_arr = np.frombuffer(result_bytes, np.uint8)
    result_img = cv2.imdecode(result_arr, cv2.IMREAD_COLOR)
    orig_arr = np.frombuffer(original_bytes, np.uint8)
    orig_img = cv2.imdecode(orig_arr, cv2.IMREAD_COLOR)
    if result_img is None or orig_img is None:
        return result_bytes
    if result_img.shape != orig_img.shape:
        result_img = cv2.resize(result_img, (orig_img.shape[1], orig_img.shape[0]))
    if mask.shape != orig_img.shape[:2]:
        mask = cv2.resize(mask, (orig_img.shape[1], orig_img.shape[0]))
    result_hsv = cv2.cvtColor(result_img, cv2.COLOR_BGR2HSV).astype(np.float32)
    orig_hsv = cv2.cvtColor(orig_img, cv2.COLOR_BGR2HSV).astype(np.float32)
    mask_f = (mask > 127).astype(np.float32)
    if mask_f.sum() == 0:
        return result_bytes
    result_mean = [result_hsv[:,:,i][mask_f > 0].mean() for i in range(3)]
    orig_mean = [orig_hsv[:,:,i][mask_f > 0].mean() for i in range(3)]
    for i in range(3):
        result_hsv[:,:,i] = result_hsv[:,:,i] - result_mean[i] + orig_mean[i]
    result_hsv = np.clip(result_hsv, 0, [180, 255, 255]).astype(np.uint8)
    result_bgr = cv2.cvtColor(result_hsv, cv2.COLOR_HSV2BGR)
    mask_3 = np.stack([mask_f] * 3, axis=-1)
    output = (result_bgr.astype(np.float32) * mask_3 +
              result_img.astype(np.float32) * (1.0 - mask_3))
    output = np.clip(output, 0, 255).astype(np.uint8)
    _, buf = cv2.imencode(".png", output)
    return buf.tobytes()


async def _get_torso_mask(se10: SE10Client, image_bytes: bytes, filename: str, image_height: int) -> str | None:
    resp = await se10.segment(
        image_bytes=image_bytes, filename=filename,
        classes="person, woman, man", box_threshold=0.20, text_threshold=0.15, mode="person",
    )
    if not resp.get("detected") or not resp.get("masks"):
        return None
    objects = resp.get("objects", [])
    masks = resp.get("masks", [])
    best_idx = max(range(len(objects)), key=lambda i: objects[i].get("area_pct", 0))
    if best_idx >= len(masks):
        return None
    import cv2
    import numpy as np
    raw = _strip_data_uri(masks[best_idx])
    arr = np.frombuffer(base64.b64decode(_fix_b64_padding(raw)), np.uint8)
    person = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if person is None:
        return None
    h, w = person.shape
    _, pw, ph = 0, w, h
    contours, _ = cv2.findContours(person, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        _, _, pw, ph = cv2.boundingRect(largest)
    # Use adaptive head detection
    head = detect_head_mask(
        orig_img=np.zeros((person.shape[0], person.shape[1], 3), dtype=np.uint8),
        person_binary=person,
        person_bbox=(0, 0, pw, ph),
        max_head_pct=0.45,
        neck_margin_below=0.50,
        dilate_kernel_size=15,
        dilate_iterations=2,
    )
    torso = cv2.bitwise_and(person, cv2.bitwise_not(head))
    coverage = (torso > 0).sum() / torso.size * 100
    if coverage < 1.0:
        return None
    _, buf = cv2.imencode(".png", torso)
    return _to_data_uri(base64.b64encode(buf).decode("utf-8"), mime="image/png")


def post_process_blend(original_bytes: bytes, inpainted_bytes: bytes, mask_uri: str, blur_ksize: int = 21) -> bytes:
    import cv2
    import numpy as np
    raw = _strip_data_uri(mask_uri)
    arr = np.frombuffer(base64.b64decode(_fix_b64_padding(raw)), np.uint8)
    mask = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    orig = cv2.imdecode(np.frombuffer(original_bytes, np.uint8), cv2.IMREAD_COLOR)
    inp = cv2.imdecode(np.frombuffer(inpainted_bytes, np.uint8), cv2.IMREAD_COLOR)
    if mask is None or orig is None or inp is None:
        return inpainted_bytes
    if inp.shape != orig.shape:
        inp = cv2.resize(inp, (orig.shape[1], orig.shape[0]))
    if mask.shape != orig.shape[:2]:
        mask = cv2.resize(mask, (orig.shape[1], orig.shape[0]))
    blurred = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (blur_ksize, blur_ksize), 0)
    blended = (inp.astype(np.float32) * blurred[:,:,np.newaxis] +
               orig.astype(np.float32) * (1.0 - blurred[:,:,np.newaxis]))
    blended = np.clip(blended, 0, 255).astype(np.uint8)
    _, buf = cv2.imencode(".png", blended)
    return buf.tobytes()


def filter_clothing_objects(objects: list[dict], masks: list[str], min_area: float = 0.1) -> tuple[list[dict], list[str]]:
    filtered_objects = []
    filtered_masks = []
    for i, obj in enumerate(objects):
        if obj.get("area_pct", 0) >= min_area and i < len(masks):
            filtered_objects.append(obj)
            filtered_masks.append(masks[i])
    return filtered_objects, filtered_masks


# ─── Progressive Mode ────────────────────────────────────────────────────────

PROGRESSIVE_PASSES = [
    {"classes": "spaghetti strap, camisole", "box_threshold": 0.06, "text_threshold": 0.04, "inpaint_strength": 0.65, "detector": "florence2", "name": "straps", "se_mode": "clothes"},
    {"classes": "top, blouse, shirt", "box_threshold": 0.08, "text_threshold": 0.05, "inpaint_strength": 0.60, "detector": "florence2", "name": "top", "se_mode": "clothes"},
    {"classes": "dress, clothing, garment", "box_threshold": 0.10, "text_threshold": 0.07, "inpaint_strength": 0.55, "detector": "florence2", "name": "full", "se_mode": "clothes"},
    {"classes": "fabric, textile, outfit", "box_threshold": 0.12, "text_threshold": 0.09, "inpaint_strength": 0.50, "detector": "florence2", "name": "cleanup", "se_mode": "clothes"},
]

PROGRESSIVE_PASSES_PERSON = [
    {"classes": "spaghetti strap, camisole", "box_threshold": 0.06, "text_threshold": 0.04, "inpaint_strength": 0.70, "detector": "florence2", "name": "straps", "se_mode": "clothes"},
    {"classes": "top, blouse, shirt", "box_threshold": 0.08, "text_threshold": 0.05, "inpaint_strength": 0.65, "detector": "florence2", "name": "top", "se_mode": "clothes"},
    {"classes": "dress, clothing, garment", "box_threshold": 0.10, "text_threshold": 0.07, "inpaint_strength": 0.60, "detector": "florence2", "name": "full", "se_mode": "clothes"},
    {"classes": "fabric, textile, outfit", "box_threshold": 0.12, "text_threshold": 0.09, "inpaint_strength": 0.55, "detector": "florence2", "name": "cleanup", "se_mode": "clothes"},
]


async def _run_progressive(job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
    """Run 4-pass progressive clothing removal."""
    se10 = SE10Client()
    se8 = SE8Client()

    try:
        image_bytes = _decode_image(job.request.image)
        logger.info("Job %s: progressive mode — image decoded (%d bytes)", job.job_id, len(image_bytes))

        current_bytes = image_bytes

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

            combined_mask = combine_masks(filtered_masks)
            combined_mask = dilate_mask(combined_mask, kernel_size=21, iterations=2)

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
                    mask_img[:int(h_img * 0.30)] = 0
                    _, buf = _cv2p.imencode(".png", mask_img)
                    combined_mask = _to_data_uri(base64.b64encode(buf).decode("utf-8"), mime="image/png")

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


# ─── Main Dispatcher ─────────────────────────────────────────────────────────

async def run_clothes_removal(job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
    mode = job.request.mode or "clothes"
    logger.info("Starting %s removal pipeline for job %s", mode, job.job_id)

    # ─── NSFW PRODUCTION: retry + pose validation + best selection ───
    if mode == "nsfw":
        logger.info("Job %s: using NSFW PRODUCTION pipeline (retry + pose validation)", job.job_id)
        from app.services.pipeline_nsfw import run_nsfw
        await run_nsfw(job, store)
        return

    # ─── NSFW TEST: experimental v2 — invert mask + low denoise + FaceID ───
    if mode == "nsfw_test":
        logger.info("Job %s: using NSFW EXPERIMENTAL pipeline (invert mask + FaceID)", job.job_id)
        from app.services.pipeline_nsfw_experimental import run_nsfw_experimental
        await run_nsfw_experimental(job, store)
        return

    # ─── Progressive mode ───
    if mode == "progressive":
        await _run_progressive(job, store)
        return

    # ─── Deprecated modes: redirect to nsfw production ───
    if mode in ("pipe_nsfw", "pipe_nsfw_subtract", "pipe_3layers", "pipe_3layers_max"):
        logger.warning("Job %s: mode '%s' DEPRECATED, redirecting to nsfw production", job.job_id, mode)
        from app.services.pipeline_nsfw import run_nsfw
        await run_nsfw(job, store)
        return

    # ─── Default: clothes/person inline mode ───
    se10 = SE10Client()
    se8 = SE8Client()

    try:
        image_bytes = _decode_image(job.request.image)
        logger.info("Job %s: image decoded (%d bytes)", job.job_id, len(image_bytes))

        from PIL import Image as PILImage
        img = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        image_height = img.size[1]

        job.status = ClothesRemovalJobStatus.DETECTING
        job.update_stage("detecting", "processing", progress=10.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        if mode == "person":
            effective_classes = job.request.classes or "person, woman, man"
        else:
            effective_classes = job.request.classes or BEST_CLOTHING_CLASSES

        t0 = time.time()

        if mode == "person":
            logger.info("Job %s: using torso mask (head subtracted) for person mode", job.job_id)
            torso_mask = await _get_torso_mask(se10, image_bytes, f"{job.job_id}.jpg", image_height)

            if torso_mask:
                filtered_masks = [torso_mask]
                filtered_objects = [{"class_name": "person_torso", "area_pct": 0, "confidence": 0, "bbox": [0, 0, 0, 0]}]
                logger.info("Job %s: using torso mask (head subtracted)", job.job_id)
            else:
                logger.warning("Job %s: torso detection failed, trying full person mask", job.job_id)
                resp = await se10.segment(
                    image_bytes=image_bytes, filename=f"{job.job_id}.jpg",
                    classes="person, woman, man", box_threshold=0.20, text_threshold=0.15, mode="person",
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
            segment_result = await se10.segment(
                image_bytes=image_bytes, filename=f"{job.job_id}.jpg",
                classes=effective_classes, box_threshold=job.request.box_threshold,
                text_threshold=0.05, mode=mode, detector=job.request.detector,
            )
            objects = segment_result.get("objects", [])
            all_masks = segment_result.get("masks", [])

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

        logger.info("Job %s: filtered to %d objects", job.job_id, len(filtered_objects))

        if not filtered_masks:
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

        job.update_stage("inpainting", "processing", progress=10.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        combined_mask = combine_masks(filtered_masks)
        combined_mask = dilate_mask(combined_mask, kernel_size=21, iterations=2)
        logger.info("Job %s: combined %d filtered masks + dilated", job.job_id, len(filtered_masks))

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

        image_b64 = _to_data_uri(base64.b64encode(image_bytes).decode("utf-8"), mime="image/jpeg")

        prompt = job.request.prompt or (DEFAULT_PERSON_PROMPT if mode == "person" else DEFAULT_CLOTHES_PROMPT)
        negative_prompt = job.request.negative_prompt or DEFAULT_CLOTHES_NEGATIVE
        inpaint_respective_field = 0.85

        raw_final = _strip_data_uri(combined_mask)
        final_arr = _np.frombuffer(base64.b64decode(_fix_b64_padding(raw_final)), _np.uint8)
        final_mask = _cv2.imdecode(final_arr, _cv2.IMREAD_GRAYSCALE)
        final_pct = (final_mask > 127).sum() / final_mask.size * 100 if final_mask is not None else 0.0

        if mode == "person":
            inpaint_strength = 0.70
            if final_pct > 50.0:
                erode_or_dilate = -5
            elif final_pct > 30.0:
                erode_or_dilate = -8
            else:
                erode_or_dilate = -10
        else:
            inpaint_strength = 0.70
            if final_pct > 30.0:
                erode_or_dilate = -20
            elif final_pct > 15.0:
                erode_or_dilate = -15
            elif final_pct > 5.0:
                erode_or_dilate = -10
            else:
                erode_or_dilate = -5

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
            logger.info("Job %s: per-garment mode (%d masks)", job.job_id, len(filtered_masks))
            result_bytes_merge = image_bytes
            for mi, single_mask in enumerate(filtered_masks):
                logger.info("Job %s: inpainting garment %d/%d", job.job_id, mi + 1, len(filtered_masks))
                single_mask_dilated = dilate_mask(single_mask, kernel_size=21, iterations=2)
                single_b64 = _to_data_uri(base64.b64encode(result_bytes_merge).decode("utf-8"), mime="image/jpeg")
                single_result = await se8.inpaint(
                    image_b64=single_b64, mask_b64=single_mask_dilated,
                    prompt=prompt, negative_prompt=negative_prompt,
                    inpaint_strength=inpaint_strength, inpaint_respective_field=inpaint_respective_field,
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
            inpaint_result = await se8.inpaint(
                image_b64=image_b64, mask_b64=combined_mask,
                prompt=prompt, negative_prompt=negative_prompt,
                inpaint_strength=inpaint_strength, inpaint_respective_field=inpaint_respective_field,
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

        logger.info("Job %s: completed — %d objects detected, result saved to %s",
            job.job_id, job.objects_detected, result_path)

        webhook_url = getattr(job.request, "webhook_url", None)
        if webhook_url:
            try:
                import httpx as _httpx
                async with _httpx.AsyncClient(timeout=10) as wh:
                    await wh.post(webhook_url, json={
                        "job_id": job.job_id, "status": "completed",
                        "result_path": result_path, "objects_detected": job.objects_detected,
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
