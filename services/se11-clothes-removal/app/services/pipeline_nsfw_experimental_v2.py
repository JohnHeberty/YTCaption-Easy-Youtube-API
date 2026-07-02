"""NSFW Experimental Pipeline V2 — Invert Mask + Low Denoise + FaceID.

COMPLETELY INDEPENDENT from pipeline.py and pipeline_nsfw.py.
All helper functions are duplicated here for isolation.

Key improvements over V1:
  - invert_mask: inpaint only clothing regions, keep face/body/background
  - Low denoising strength (0.35) preserves structure
  - IP-Adapter FaceID preserves facial identity
  - Clothes-neutral IP-Adapter ref preserves pose/body
  - OpenPose ControlNet for structural conditioning
  - Optional face restore (CodeFormer/GFPGAN)
"""
from __future__ import annotations

import base64
import json
import os
import time

import cv2 as _cv2
import numpy as _np

from common.log_utils import get_logger
from common.datetime_utils import now_brazil

from app.core.config import settings
from app.core.models import ClothesRemovalJob, ClothesRemovalJobStatus
from app.infrastructure.http_client import SE10Client, SE8Client
from app.infrastructure.redis_store import ClothesRemovalJobStore
from app.validators.pose_detector import detect_pose, compare_poses, render_pose_stick_figure

logger = get_logger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

DEFAULT_CLOTHES_NEGATIVE = (
    "clothes, fabric, bra, straps, underwear, top, blouse, shirt, "
    "dress, skirt, pattern, floral, textile, garment, "
    "face on body, extra face, duplicate face, second face, face on chest, "
    "face on torso, multiple faces, two faces, "
    "text, watermark, deformed, blurry, cartoon, anime, painting, CGI, "
    "extra limbs, disfigured, poorly drawn face, mutated hands, "
    "bad anatomy, deformed skin, wrinkled, scarred"
)

NSFW_PROMPT = (
    "NSFW, NSFW, NSFW, NSFW, NSFW, solo, bare skin, no clothing, naked body, "
    "detailed breast anatomy, realistic nipples, areola details, "
    "natural skin pores, skin texture, skin imperfections, "
    "realistic body proportions, maintaining exact same body posture, "
    "keeping original body position, not moving, not rotating, same stance, identical pose, "
    "skin tone matching the person's arms and face, consistent skin color throughout, "
    "seamless skin transition, matching skin tone with surrounding body, "
    "photorealistic, professional studio photography, soft lighting, "
    "sharp focus, raw photo, highly detailed, hyperrealistic, 8k uhd"
)

NSFW_LORAS = [
    {"enabled": True, "model_name": "NsfwPovAllInOneLoraSdxl-000009.safetensors", "weight": 0.3},
    {"enabled": True, "model_name": "sd_xl_offset_example-lora_1.0.safetensors", "weight": 0.1},
    {"enabled": True, "model_name": "add-detail-xl.safetensors", "weight": 1.0},
    {"enabled": True, "model_name": "None", "weight": 1.0},
    {"enabled": True, "model_name": "None", "weight": 1.0},
]

CLOTHES_CLASSES = (
    "spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, "
    "clothing, garment, skirt, pants, shorts, jeans, sweater, jacket, "
    "coat, hoodie, t-shirt"
)

# ─── Multidimensional Scoring Weights ────────────────────────────────────────
# Lower score = better. Each metric is normalized to [0, 100] range.
# skin_ratio:     result_skin_pct / original_skin_pct (>1.0 = more skin exposed = GOOD)
#                 We use (1 - skin_ratio) so lower = better (more skin = lower score)
# head_avg:       face landmark drift (lower = face more preserved)
# clothes_pct:    residual clothing on RESULT (lower = better removal)
# max_landmark:   worst single landmark drift (lower = more stable pose)
SCORE_W_SKIN = 0.40        # Skin exposure (primary quality metric)
SCORE_W_HEAD = 0.30        # Face preservation
SCORE_W_LANDMARK = 0.20    # Overall pose stability
SCORE_W_CLOTHES = 0.10     # Clothing residual (low weight — SE10 can be unreliable)
SCORE_EARLY_STOP = 5.0     # Stop early if composite score < this


# ─── Helpers ─────────────────────────────────────────────────────────────────

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


def _combine_masks(masks: list[str], orig_h: int, orig_w: int) -> _np.ndarray | None:
    """Combine multiple base64 masks into a single binary mask."""
    combined = None
    for mb in masks:
        raw = _strip_data_uri(mb)
        c_bytes = base64.b64decode(_fix_b64_padding(raw))
        cm = _cv2.imdecode(_np.frombuffer(c_bytes, _np.uint8), _cv2.IMREAD_GRAYSCALE)
        if cm is None:
            continue
        if cm.shape[:2] != (orig_h, orig_w):
            cm = _cv2.resize(cm, (orig_w, orig_h))
        cb = (cm > 127).astype(_np.uint8) * 255
        combined = cb if combined is None else _cv2.bitwise_or(combined, cb)
    return combined


async def _detect_result_clothes(
    se10: SE10Client,
    inpainted_img: _np.ndarray,
    orig_h: int,
    orig_w: int,
) -> float:
    """Detect residual clothing on an inpainted result image.

    Returns clothes_pct (0.0 = no clothes detected, higher = more clothes remain).
    This is used for multidimensional scoring — lower is better.
    """
    try:
        _, result_buf = _cv2.imencode(".jpg", inpainted_img, [_cv2.IMWRITE_JPEG_QUALITY, 90])
        result_bytes = result_buf.tobytes()
        result_seg = await se10.segment(
            image_bytes=result_bytes,
            filename="result.jpg",
            classes=CLOTHES_CLASSES,
            box_threshold=0.06,
            text_threshold=0.04,
            mode="clothes",
        )
        if result_seg.get("detected") and result_seg.get("masks"):
            result_mask = _combine_masks(result_seg["masks"], orig_h, orig_w)
            if result_mask is not None:
                return float((result_mask > 0).sum() / result_mask.size * 100)
        return 0.0
    except Exception as exc:
        logger.warning("Result clothes detection failed: %s", exc)
        return 0.0


def _detect_skin_hsv(img: _np.ndarray) -> float:
    """Detect skin exposure using HSV color range.

    Returns skin_pct (0.0-100.0) — percentage of image pixels classified as skin.
    This is a LOCAL, FAST detection (no SE10 call needed).

    HSV range tuned for diverse skin tones:
      H: 0-30 (warm hues)
      S: 15-170 (moderate saturation — excludes white/grey)
      V: 60-255 (excludes very dark shadows)
    """
    hsv = _cv2.cvtColor(img, _cv2.COLOR_BGR2HSV)
    lower_skin = _np.array([0, 15, 60], dtype=_np.uint8)
    upper_skin = _np.array([30, 170, 255], dtype=_np.uint8)
    skin_mask = _cv2.inRange(hsv, lower_skin, upper_skin)

    # Clean up noise with morphological operations
    kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))
    skin_mask = _cv2.morphologyEx(skin_mask, _cv2.MORPH_OPEN, kernel, iterations=1)
    skin_mask = _cv2.morphologyEx(skin_mask, _cv2.MORPH_CLOSE, kernel, iterations=2)

    return float((skin_mask > 0).sum() / skin_mask.size * 100)


def _compute_composite_score(
    skin_ratio: float,
    head_avg: float,
    clothes_pct: float,
    max_landmark: float,
) -> float:
    """Compute composite score from four metrics (lower = better).

    skin_ratio: result_skin_pct / original_skin_pct (>1.0 = more skin = GOOD)
                We use (1 - skin_ratio) so that more skin → lower score → better.
    head_avg:   face landmark drift (lower = better)
    clothes_pct: residual clothing (lower = better)
    max_landmark: worst landmark drift (lower = better)
    """
    # Skin score: (1 - ratio) so more skin = lower (better)
    # If ratio=2.0 (2x more skin), skin_score = -1.0 (very good)
    # If ratio=0.5 (half the skin), skin_score = 0.5 (bad)
    # If ratio=1.0 (same skin), skin_score = 0.0 (neutral)
    skin_score = 1.0 - skin_ratio

    head_clamped = min(head_avg, 100.0)
    clothes_clamped = min(clothes_pct, 100.0)
    landmark_clamped = min(max_landmark, 100.0)

    score = (
        SCORE_W_SKIN * skin_score +
        SCORE_W_HEAD * head_clamped +
        SCORE_W_LANDMARK * landmark_clamped +
        SCORE_W_CLOTHES * clothes_clamped
    )
    return round(score, 3)


def _build_clothes_neutral_ref(
    orig_img: _np.ndarray,
    clothes_mask: _np.ndarray,
    person_binary: _np.ndarray,
) -> _np.ndarray:
    """Build a clothes-neutral reference image for IP-Adapter.

    Replaces clothing region with average skin tone + subtle noise
    so CLIP encoder sees pose/body but NOT clothing texture.
    """
    h, w = orig_img.shape[:2]
    ref = orig_img.copy()

    # Find exposed skin pixels (person minus clothes)
    exposed = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(clothes_mask))
    exposed_pixels = ref[exposed > 0]
    if len(exposed_pixels) == 0:
        return ref

    # Average skin tone in BGR
    skin_bgr = _np.mean(exposed_pixels, axis=0).astype(_np.uint8)

    # Erode clothes mask 5px to avoid edge bleeding
    erode_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))
    clothes_eroded = _cv2.erode(clothes_mask, erode_k, iterations=1)

    # Fill clothing region with skin tone + subtle noise
    fill_mask = clothes_eroded > 127
    noise = _np.random.randint(-8, 9, ref[fill_mask].shape, dtype=_np.int16)
    filled = _np.clip(
        ref[fill_mask].astype(_np.int16) + noise,
        0, 255
    ).astype(_np.uint8)
    ref[fill_mask] = filled

    # Blur the filled region for natural transition
    blur_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (15, 15))
    blurred = _cv2.GaussianBlur(ref, (15, 15), 5.0)

    # Only apply blur to clothing region
    clothes_f = clothes_mask.astype(_np.float32) / 255.0
    ref = (ref.astype(_np.float32) * (1.0 - clothes_f[:, :, None]) +
           blurred.astype(_np.float32) * clothes_f[:, :, None])
    ref = _np.clip(ref, 0, 255).astype(_np.uint8)

    return ref


# ─── Main Entry Point ────────────────────────────────────────────────────────

async def run_nsfw_experimental_v2(
    job: ClothesRemovalJob,
    store: ClothesRemovalJobStore,
) -> None:
    """NSFW Experimental V2 — Invert Mask + Low Denoise + FaceID.

    FLUXO:
    1. SE10: Person detection
    2. SE10: Clothes detection (Florence-2)
    3. InsightFace: extract face embedding for FaceID
    4. Build invert mask (clothes region = white = inpaint)
    5. Build clothes-neutral IP-Adapter ref
    6. SE8: Inpaint with invert_mask + low denoise + FaceID + neutral ref
    7. Optional face restore via SE8
    8. Save debug masks + metadata
    9. Copy result to show/
    """
    se10 = SE10Client()
    se8 = SE8Client()

    try:
        image_bytes = _decode_image(job.request.image)
        logger.info("Job %s: nsfw_test V2 started", job.job_id)

        orig_img = _cv2.imdecode(
            _np.frombuffer(image_bytes, _np.uint8), _cv2.IMREAD_COLOR
        )
        if orig_img is None:
            raise ValueError("Failed to decode image")
        orig_h, orig_w = orig_img.shape[:2]

        # Output directory
        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)

        def _save_debug(num: int, name: str, img: _np.ndarray) -> None:
            try:
                path = os.path.join(output_dir, f"{num:02d}_{name}.png")
                _cv2.imwrite(path, img)
            except Exception as exc:
                logger.warning("Job %s: debug save %s failed: %s", job.job_id, name, exc)

        # ─── Stage 1: Person Detection ───────────────────────────────────
        job.update_stage("detecting", "processing", progress=10.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        person_seg = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}_person.jpg",
            classes="person, woman, man",
            box_threshold=0.20,
            text_threshold=0.15,
            mode="person",
        )

        if not person_seg.get("detected") or not person_seg.get("masks"):
            job.status = ClothesRemovalJobStatus.COMPLETED
            job.error = "No person detected"
            job.progress = 100.0
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        best_idx = max(
            range(len(person_seg["objects"])),
            key=lambda i: person_seg["objects"][i].get("area_pct", 0),
        )
        raw_p = _strip_data_uri(person_seg["masks"][best_idx])
        person_mask = _cv2.imdecode(
            _np.frombuffer(base64.b64decode(_fix_b64_padding(raw_p)), _np.uint8),
            _cv2.IMREAD_GRAYSCALE,
        )
        if person_mask is None:
            raise ValueError("Bad person mask")
        if person_mask.shape[:2] != (orig_h, orig_w):
            person_mask = _cv2.resize(person_mask, (orig_w, orig_h))
        person_binary = (person_mask > 127).astype(_np.uint8) * 255

        # Fill internal holes
        _h, _w = person_binary.shape
        _flood = person_binary.copy()
        _flood_mask = _np.zeros((_h + 2, _w + 2), _np.uint8)
        _cv2.floodFill(_flood, _flood_mask, (0, 0), 255)
        _holes = _cv2.bitwise_not(_flood)
        person_binary = _cv2.bitwise_or(person_binary, _holes)

        _save_debug(0, "original", orig_img)
        _save_debug(1, "person", person_binary)
        logger.info("Job %s: person detected (%.1f%% coverage)",
                     job.job_id, (person_binary > 0).sum() / person_binary.size * 100)

        # ─── Stage 2: Clothes Detection (Florence-2) ────────────────────
        job.update_stage("detecting", "processing", progress=25.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        clothes_seg = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}_clothes.jpg",
            classes=CLOTHES_CLASSES,
            box_threshold=0.06,
            text_threshold=0.04,
            mode="clothes",
            detector="florence2",
        )

        clothes_combined = None
        if clothes_seg.get("detected") and clothes_seg.get("masks"):
            clothes_combined = _combine_masks(clothes_seg["masks"], orig_h, orig_w)

        if clothes_combined is None:
            # Fallback: use body mask as inpaint mask
            logger.warning("Job %s: no clothes detected, using body mask fallback", job.job_id)
            clothes_combined = person_binary.copy()

        clothes_pct = (clothes_combined > 0).sum() / clothes_combined.size * 100
        _save_debug(2, "clothes_raw", clothes_combined)
        logger.info("Job %s: clothes detected (%.1f%% coverage)", job.job_id, clothes_pct)

        # Save individual garment masks from SE10
        if clothes_seg.get("detected") and clothes_seg.get("masks"):
            for gi, (gm_b64, gobj) in enumerate(zip(clothes_seg["masks"], clothes_seg.get("objects", []))):
                try:
                    raw_gm = _strip_data_uri(gm_b64)
                    gm_img = _cv2.imdecode(
                        _np.frombuffer(base64.b64decode(_fix_b64_padding(raw_gm)), _np.uint8),
                        _cv2.IMREAD_GRAYSCALE,
                    )
                    if gm_img is not None:
                        if gm_img.shape[:2] != (orig_h, orig_w):
                            gm_img = _cv2.resize(gm_img, (orig_w, orig_h))
                        gclass = gobj.get("class_name", f"garment_{gi}")
                        garea = gobj.get("area_pct", 0)
                        gm_color = _cv2.cvtColor(gm_img, _cv2.COLOR_GRAY2BGR)
                        _cv2.putText(gm_color, f"{gclass} ({garea:.1f}%)", (10, 25),
                                     _cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        _save_debug(20 + gi, f"garment_{gi}_{gclass}", gm_color)
                except Exception:
                    pass

            # Save SE10 detection metadata
            try:
                import json as _json
                seg_meta = {
                    "person": {
                        "detected": bool(person_seg.get("detected")),
                        "coverage_pct": float(round((person_binary > 0).sum() / person_binary.size * 100, 1)),
                        "objects": person_seg.get("objects", []),
                    },
                    "clothes": {
                        "detected": bool(clothes_seg.get("detected")),
                        "coverage_pct": float(round(clothes_pct, 1)),
                        "num_garments": len(clothes_seg.get("objects", [])),
                        "objects": clothes_seg.get("objects", []),
                    },
                    "image_size": {"width": orig_w, "height": orig_h},
                }
                with open(os.path.join(output_dir, "detection_meta.json"), "w") as f:
                    _json.dump(seg_meta, f, indent=2)
            except Exception:
                pass

        # ─── Stage 3: InsightFace Embedding ─────────────────────────────
        job.update_stage("detecting", "processing", progress=30.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        faceid_embedding = None
        if getattr(job.request, "use_faceid", True):
            from app.services.faceid_extractor import extract_faceid_embedding
            faceid_embedding = extract_faceid_embedding(orig_img, person_binary)
            if faceid_embedding:
                logger.info("Job %s: FaceID embedding extracted (512-d)", job.job_id)
            else:
                logger.warning("Job %s: FaceID extraction failed, continuing without", job.job_id)

        # ─── Stage 4: Build Invert Mask ─────────────────────────────────
        job.update_stage("detecting", "processing", progress=35.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        inpaint_mode = getattr(job.request, "inpaint_mode", "invert_mask")

        if inpaint_mode == "invert_mask":
            # ─── SIMPLE CLOTHES MASK: only clothing area + light margin ───
            # Original plan (UPGRADE.md §4.4): clothes_mask + dilate(15px)
            # Keeps pose intact because SE8 only regenerates clothing pixels.
            inpaint_mask = clothes_combined.copy()
            dilate_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (15, 15))
            inpaint_mask = _cv2.dilate(inpaint_mask, dilate_k, iterations=1)

            # ─── SUBTRACT HEAD+HAIR REGION to protect face and hair ───
            from app.services.head_detector import detect_head_mask
            contours, _ = _cv2.findContours(person_binary, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest = max(contours, key=_cv2.contourArea)
                px, py, pw, ph = _cv2.boundingRect(largest)
                head_mask = detect_head_mask(
                    orig_img=orig_img,
                    person_binary=person_binary,
                    person_bbox=(px, py, pw, ph),
                    max_head_pct=0.45,
                    neck_margin_below=0.50,
                    dilate_kernel_size=25,
                    dilate_iterations=3,
                    expand_up=2.5,
                    expand_w=0.8,
                )
                inpaint_mask = _cv2.bitwise_and(inpaint_mask, _cv2.bitwise_not(head_mask))
                logger.info("Job %s: head+hair mask subtracted from inpaint mask", job.job_id)

        elif inpaint_mode == "clothes_mask":
            inpaint_mask = clothes_combined.copy()
            dilate_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (21, 21))
            inpaint_mask = _cv2.dilate(inpaint_mask, dilate_k, iterations=2)

        else:
            # body_mask (legacy)
            from app.services.head_detector import detect_head_mask
            contours, _ = _cv2.findContours(person_binary, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                raise ValueError("No contours")
            largest = max(contours, key=_cv2.contourArea)
            px, py, pw, ph = _cv2.boundingRect(largest)

            head_mask = detect_head_mask(
                orig_img=orig_img,
                person_binary=person_binary,
                person_bbox=(px, py, pw, ph),
                max_head_pct=0.45,
                neck_margin_below=0.50,
                dilate_kernel_size=15,
                dilate_iterations=2,
            )
            inpaint_mask = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(head_mask))
            dilate_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (15, 15))
            inpaint_mask = _cv2.dilate(inpaint_mask, dilate_k, iterations=2)

        inpaint_pct = (inpaint_mask > 0).sum() / inpaint_mask.size * 100
        _save_debug(3, f"inpaint_mask_{inpaint_mode}", inpaint_mask)
        clothes_orig_pct = (clothes_combined > 0).sum() / clothes_combined.size * 100
        logger.info("Job %s: mask=%s inpaint=%.1f%% clothes_orig=%.1f%%",
                     job.job_id, inpaint_mode, inpaint_pct, clothes_orig_pct)

        # Save mask overlay on original for visual debugging
        try:
            mask_overlay = orig_img.copy()
            mask_color = _cv2.cvtColor(inpaint_mask, _cv2.COLOR_GRAY2BGR)
            mask_color[:, :, 0] = 0   # no blue
            mask_color[:, :, 2] = 0   # no red → green channel = inpaint region
            mask_overlay = _cv2.addWeighted(mask_overlay, 0.6, mask_color, 0.4, 0)
            _cv2.putText(mask_overlay,
                         f"Inpaint mask: {inpaint_pct:.1f}% | clothes: {clothes_orig_pct:.1f}%",
                         (10, 25), _cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            _cv2.putText(mask_overlay, f"Mode: {inpaint_mode}",
                         (10, 50), _cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            _save_debug(30, "mask_overlay", mask_overlay)
        except Exception:
            pass

        # ─── Stage 5: Build Clothes-Neutral IP-Adapter Ref ──────────────
        job.update_stage("inpainting", "processing", progress=40.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        ref_img = _build_clothes_neutral_ref(orig_img, clothes_combined, person_binary)
        _save_debug(4, "neutral_ref", ref_img)

        _, ref_buf = _cv2.imencode(".png", ref_img)
        ref_b64 = _to_data_uri(base64.b64encode(ref_buf).decode("utf-8"), mime="image/png")

        _, mask_buf = _cv2.imencode(".png", inpaint_mask)
        mask_b64 = _to_data_uri(base64.b64encode(mask_buf).decode("utf-8"), mime="image/png")

        image_b64 = _to_data_uri(base64.b64encode(image_bytes).decode("utf-8"), mime="image/jpeg")

        # ─── Stage 6: Detect Original Pose (once) ────────────────────────
        orig_pose = None
        try:
            orig_pose = detect_pose(orig_img, min_detection_confidence=0.5)
            if orig_pose:
                logger.info("Job %s: original pose detected (%d landmarks)",
                            job.job_id, len(orig_pose.landmarks))
                # Save pose landmarks overlay on original
                try:
                    pose_overlay = orig_img.copy()
                    for lm in orig_pose.landmarks:
                        if lm.visibility > 0.5:
                            color = (0, 255, 0)
                            if lm.index in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
                                color = (255, 255, 0)  # head = yellow
                            _cv2.circle(pose_overlay, (int(lm.x), int(lm.y)), 4, color, -1)
                    # Draw connections
                    import mediapipe as mp
                    mp_pose = mp.solutions.pose
                    for conn in mp_pose.POSE_CONNECTIONS:
                        lm1 = orig_pose.landmarks[conn[0].value]
                        lm2 = orig_pose.landmarks[conn[1].value]
                        if lm1.visibility > 0.5 and lm2.visibility > 0.5:
                            _cv2.line(pose_overlay, (int(lm1.x), int(lm1.y)),
                                      (int(lm2.x), int(lm2.y)), (0, 255, 0), 2)
                    _cv2.putText(pose_overlay, f"Pose: {len(orig_pose.landmarks)} landmarks",
                                (10, 25), _cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    _save_debug(6, "pose_landmarks", pose_overlay)
                except Exception:
                    pass
            else:
                logger.warning("Job %s: no pose detected in original, pose validation disabled", job.job_id)
        except Exception as exc:
            logger.warning("Job %s: pose detection failed: %s — disabling validation", job.job_id, exc)

        # ─── Stage 6b: Build OpenPose Stick Figure ──────────────────────
        # Generate once before attempt loop (same pose for all attempts)
        openpose_b64 = None
        if orig_pose is not None:
            try:
                openpose_img = render_pose_stick_figure(orig_pose, thickness=4)
                _save_debug(5, "openpose", openpose_img)
                _, op_buf = _cv2.imencode(".png", openpose_img)
                openpose_b64 = _to_data_uri(base64.b64encode(op_buf).decode("utf-8"), mime="image/png")
                logger.info("Job %s: OpenPose stick figure generated", job.job_id)
            except Exception as exc:
                logger.warning("Job %s: OpenPose generation failed: %s", job.job_id, exc)

        # ─── Stage 7: SE8 Inpaint (5 Attempts + Pose Validation) ────────
        job.update_stage("inpainting", "processing", progress=50.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        base_strength = getattr(job.request, "test_inpaint_strength", 0.86) or 0.86
        faceid_weight = getattr(job.request, "faceid_weight", 0.8) or 0.8
        base_model = getattr(job.request, "base_model", "lustifySDXLNSFW_v20-inpainting.safetensors")
        max_attempts = 5
        best_result = None
        best_score = float("inf")
        best_pose_meta = None
        all_attempts_meta = []
        all_poses_changed = True

        # Compute original skin_pct as baseline for skin_ratio scoring
        original_skin_pct = _detect_skin_hsv(orig_img)
        logger.info("Job %s: original skin_pct=%.1f%% (HSV baseline)", job.job_id, original_skin_pct)

        for attempt in range(1, max_attempts + 1):
            strength = base_strength + 0.03 * (attempt - 1)
            logger.info("Job %s: SE8 attempt %d/%d — strength=%.2f field=0.55 FaceID=%s",
                        job.job_id, attempt, max_attempts, strength,
                        "on" if faceid_embedding else "off")

            image_prompts = [
                {"cn_img": ref_b64, "cn_stop": 0.5, "cn_weight": 0.8, "cn_type": "ImagePrompt"},
            ]
            # OpenPose ControlNet incompatible with LustifyNSFW (different UNet architecture)
            if openpose_b64 and "juggernaut" in base_model.lower():
                image_prompts.append(
                    {"cn_img": openpose_b64, "cn_stop": 0.6, "cn_weight": 0.5, "cn_type": "OpenPose"}
                )

            t0 = time.time()
            result = await se8.inpaint(
                image_b64=image_b64,
                mask_b64=mask_b64,
                prompt=NSFW_PROMPT,
                negative_prompt=DEFAULT_CLOTHES_NEGATIVE,
                inpaint_strength=strength,
                inpaint_respective_field=0.55,
                inpaint_erode_or_dilate=0,
                loras=NSFW_LORAS,
                image_prompts=image_prompts,
                base_model=base_model,
                invert_mask=True,
                ip_adapter_faceid_embeds=faceid_embedding,
                ip_adapter_faceid_weight=faceid_weight,
            )
            elapsed = time.time() - t0

            if not result or not result.get("base64"):
                logger.warning("Job %s: attempt %d empty (%.1fs)", job.job_id, attempt, elapsed)
                all_attempts_meta.append({
                    "attempt": attempt, "strength": strength,
                    "status": "empty", "pose_score": 999.0,
                })
                if attempt < max_attempts:
                    import asyncio
                    await asyncio.sleep(3 * attempt)
                continue

            inpainted_bytes = base64.b64decode(result["base64"])
            inpainted_img = _cv2.imdecode(
                _np.frombuffer(inpainted_bytes, _np.uint8), _cv2.IMREAD_COLOR
            )
            if inpainted_img is None:
                logger.warning("Job %s: attempt %d bad decode", job.job_id, attempt)
                all_attempts_meta.append({
                    "attempt": attempt, "strength": strength,
                    "status": "bad_decode", "pose_score": 999.0,
                })
                continue

            if inpainted_img.shape[:2] != (orig_h, orig_w):
                inpainted_img = _cv2.resize(inpainted_img, (orig_w, orig_h))

            # ─── Pose Validation ───
            # Focus on HEAD stability (face preservation) — limbs WILL change
            # because we're regenerating the body. Use non-strict mode with
            # reasonable thresholds: head>3% or torso>8% = pose_changed.
            pose_score = 999.0
            pose_changed = True
            pose_meta = {}
            head_avg = 0.0
            torso_avg = 0.0
            limbs_avg = 0.0
            max_landmark = 0.0
            if orig_pose is not None:
                try:
                    result_pose = detect_pose(inpainted_img, min_detection_confidence=0.5)
                    if result_pose:
                        comparison = compare_poses(
                            orig_pose, result_pose,
                            strict=False,
                            head_threshold_pct=3.0,
                            torso_threshold_pct=8.0,
                            limbs_threshold_pct=30.0,
                        )
                        pose_changed = comparison.pose_changed

                        head_diffs = [d.distance_normalized for d in comparison.diffs if d.group == "HEAD"]
                        torso_diffs = [d.distance_normalized for d in comparison.diffs if d.group == "TORSO"]
                        limb_diffs = [d.distance_normalized for d in comparison.diffs if d.group == "LIMB"]

                        head_avg = float(_np.mean(head_diffs)) if head_diffs else 0.0
                        torso_avg = float(_np.mean(torso_diffs)) if torso_diffs else 0.0
                        limbs_avg = float(_np.mean(limb_diffs)) if limb_diffs else 0.0
                        max_landmark = float(max(
                            (d.distance_normalized for d in comparison.diffs), default=0.0
                        ))

                        # Score = head change (lower is better, face should stay same)
                        pose_score = head_avg

                        pose_meta = {
                            "pose_changed": bool(pose_changed),
                            "head_pct": round(head_avg, 3),
                            "torso_pct": round(torso_avg, 3),
                            "limbs_pct": round(limbs_avg, 3),
                            "max_landmark_pct": round(max_landmark, 3),
                        }
                        if not pose_changed:
                            all_poses_changed = False
                        logger.info("Job %s: attempt %d pose — changed=%s head=%.3f%% torso=%.3f%% limbs=%.3f%%",
                                    job.job_id, attempt, pose_changed, head_avg, torso_avg, limbs_avg)
                    else:
                        logger.warning("Job %s: attempt %d no pose detected in result", job.job_id, attempt)
                except Exception as exc:
                    logger.warning("Job %s: attempt %d pose validation error: %s", job.job_id, attempt, exc)

            # ─── Result Clothes Detection (for multidimensional scoring) ───
            result_clothes_pct = await _detect_result_clothes(se10, inpainted_img, orig_h, orig_w)

            # ─── Result Skin Detection (HSV-based, local & fast) ───
            result_skin_pct = _detect_skin_hsv(inpainted_img)
            skin_ratio = result_skin_pct / original_skin_pct if original_skin_pct > 0 else 1.0

            logger.info("Job %s: attempt %d clothes=%.1f%% skin=%.1f%% (ratio=%.2f)",
                        job.job_id, attempt, result_clothes_pct, result_skin_pct, skin_ratio)

            # ─── Composite Score ───
            # 4 metrics: skin_ratio (more=better), head (lower=better), landmark (lower=better), clothes (lower=better)
            # Weights: skin=0.4, head=0.3, landmark=0.2, clothes=0.1
            composite_score = _compute_composite_score(
                skin_ratio=skin_ratio,
                head_avg=head_avg,
                clothes_pct=result_clothes_pct,
                max_landmark=max_landmark,
            )

            attempt_meta = {
                "attempt": attempt,
                "strength": float(strength),
                "status": "ok",
                "pose_score": float(pose_score),
                "pose_changed": bool(pose_changed),
                "result_clothes_pct": round(result_clothes_pct, 3),
                "result_skin_pct": round(result_skin_pct, 3),
                "skin_ratio": round(skin_ratio, 3),
                "composite_score": float(composite_score),
                **pose_meta,
            }
            all_attempts_meta.append(attempt_meta)

            _save_debug(50 + attempt,
                        f"try_{attempt}_s{strength:.2f}_cs{composite_score:.2f}_cl{result_clothes_pct:.1f}_{'OK' if not pose_changed else 'CHG'}",
                        inpainted_img)

            logger.info("Job %s: attempt %d done composite=%.3f head=%.3f clothes=%.1f landmark=%.3f (%.1fs)",
                        job.job_id, attempt, composite_score, head_avg, result_clothes_pct, max_landmark, elapsed)

            if composite_score < best_score:
                best_score = composite_score
                best_result = inpainted_img.copy()
                best_pose_meta = attempt_meta.copy()

            # Early stop if composite score is excellent (face preserved + clothes removed)
            if composite_score < SCORE_EARLY_STOP:
                logger.info("Job %s: excellent composite score (%.3f < %.1f), stopping early",
                            job.job_id, composite_score, SCORE_EARLY_STOP)
                break

        if best_result is None:
            job.status = ClothesRemovalJobStatus.FAILED
            job.error = "SE8 returned empty results after all attempts"
            job.updated_at = now_brazil()
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        composited = best_result.copy()

        # ─── Stage 8: Face Restore (on best result only) ─────────────────
        job.update_stage("inpainting", "processing", progress=80.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        face_restore_enabled = getattr(job.request, "face_restore", False)

        if face_restore_enabled:
            restore_model = getattr(job.request, "face_restore_model", "CodeFormer")
            restore_fidelity = getattr(job.request, "face_restore_fidelity", 0.5)
            logger.info("Job %s: applying face restore (%s, fidelity=%.2f) on best result",
                        job.job_id, restore_model, restore_fidelity)
            try:
                _, comp_buf = _cv2.imencode(".png", composited)
                comp_b64 = _to_data_uri(base64.b64encode(comp_buf).decode("utf-8"), mime="image/png")
                restore_result = await se8.restore_face(
                    image_b64=comp_b64,
                    model=restore_model,
                    fidelity=restore_fidelity,
                )
                if restore_result and restore_result.get("base64"):
                    restored_bytes = base64.b64decode(restore_result["base64"])
                    restored_img = _cv2.imdecode(
                        _np.frombuffer(restored_bytes, _np.uint8), _cv2.IMREAD_COLOR
                    )
                    if restored_img is not None:
                        if restored_img.shape[:2] != (orig_h, orig_w):
                            restored_img = _cv2.resize(restored_img, (orig_w, orig_h))
                        composited = restored_img
                        _save_debug(60, "face_restored", composited)
                        logger.info("Job %s: face restore done (faces=%s)",
                                    job.job_id, restore_result.get("faces_detected", "?"))
            except Exception as exc:
                logger.warning("Job %s: face restore failed: %s", job.job_id, exc)

        # ─── Stage 9: Save Results ──────────────────────────────────────
        job.update_stage("inpainting", "processing", progress=95.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        result_path = os.path.join(output_dir, f"{job.job_id}_result.png")
        _, fb = _cv2.imencode(".png", composited)
        with open(result_path, "wb") as f:
            f.write(fb.tobytes())

        # Save debug overlay
        try:
            overlay = orig_img.copy()
            ov_mask = _cv2.cvtColor(inpaint_mask, _cv2.COLOR_GRAY2BGR)
            ov_mask[:, :, 0] = 0
            ov_mask[:, :, 2] = 0
            overlay = _cv2.addWeighted(overlay, 0.5, ov_mask, 0.5, 0)
            pose_status = "POSE_OK" if best_pose_meta and not best_pose_meta.get("pose_changed") else "POSE_CHANGED"
            _cv2.putText(
                overlay,
                f"V2 str={base_strength:.2f} FaceID={'on' if faceid_embedding else 'off'} {pose_status}",
                (10, 30), _cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1,
            )
            _cv2.putText(
                overlay,
                f"composite={best_score:.3f} skin_ratio={best_pose_meta.get('skin_ratio', 0):.2f} head={best_pose_meta.get('head_pct', 0):.2f}%",
                (10, 55), _cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1,
            )
            _cv2.imwrite(os.path.join(output_dir, f"{job.job_id}_debug_overlay.png"), overlay)
        except Exception as exc:
            logger.warning("Job %s: overlay save failed: %s", job.job_id, exc)

        # Metadata
        meta = {
            "mode": "nsfw_test_v2",
            "scoring": "multidimensional_v2",
            "scoring_weights": {
                "skin": SCORE_W_SKIN,
                "head": SCORE_W_HEAD,
                "landmark": SCORE_W_LANDMARK,
                "clothes": SCORE_W_CLOTHES,
            },
            "inpaint_mode": inpaint_mode,
            "strength": float(base_strength),
            "faceid": faceid_embedding is not None,
            "faceid_weight": float(faceid_weight),
            "face_restore": face_restore_enabled,
            "original_skin_pct": float(round(original_skin_pct, 1)),
            "attempts": len(all_attempts_meta),
            "best_composite_score": float(best_score),
            "best_skin_ratio": float(best_pose_meta.get("skin_ratio", 0.0)) if best_pose_meta else 0.0,
            "best_result_skin_pct": float(best_pose_meta.get("result_skin_pct", 0.0)) if best_pose_meta else 0.0,
            "best_head_pct": float(best_pose_meta.get("head_pct", 0.0)) if best_pose_meta else 0.0,
            "best_clothes_pct": float(best_pose_meta.get("result_clothes_pct", 0.0)) if best_pose_meta else 0.0,
            "best_max_landmark_pct": float(best_pose_meta.get("max_landmark_pct", 0.0)) if best_pose_meta else 0.0,
            "best_pose_changed": bool(best_pose_meta.get("pose_changed", True)) if best_pose_meta else True,
            "all_poses_changed": bool(all_poses_changed),
            "person_coverage": float(round((person_binary > 0).sum() / person_binary.size * 100, 1)),
            "clothes_coverage": float(round(clothes_pct, 1)),
            "inpaint_coverage": float(round(inpaint_pct, 1)),
            "attempts_detail": all_attempts_meta,
        }
        with open(os.path.join(output_dir, "v2_meta.json"), "w") as ef:
            json.dump(meta, ef, indent=2)

        # Copy to show/
        try:
            show_dir = "/root/YTCaption-Easy-Youtube-API/show"
            os.makedirs(show_dir, exist_ok=True)
            _cv2.imwrite(os.path.join(show_dir, f"v2_{job.job_id}_result.png"), composited)
            logger.info("Job %s: result copied to show/", job.job_id)
        except Exception as exc:
            logger.warning("Job %s: show/ copy failed: %s", job.job_id, exc)

        # ─── Done ───────────────────────────────────────────────────────
        job.result_path = result_path
        job.status = ClothesRemovalJobStatus.COMPLETED
        job.progress = 100.0
        job.objects_detected = 1
        job.update_stage("inpainting", "completed", progress=100.0)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))
        logger.info("Job %s: nsfw_test V2 completed — %s (composite=%.3f, skin_ratio=%.2f, head=%.3f%%, attempts=%d)",
                     job.job_id, result_path, best_score,
                     best_pose_meta.get("skin_ratio", 0.0) if best_pose_meta else 0.0,
                     best_pose_meta.get("head_pct", 0.0) if best_pose_meta else 0.0,
                     len(all_attempts_meta))

    except Exception as e:
        logger.error("Job %s nsfw_test V2 failed: %s", job.job_id, e, exc_info=True)
        job.status = ClothesRemovalJobStatus.FAILED
        job.error = str(e)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

    finally:
        await se10.close()
        await se8.close()
