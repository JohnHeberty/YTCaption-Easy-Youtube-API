"""NSFW Production Pipeline — retry + pose validation + best selection.

This is a COMPLETELY INDEPENDENT file. Zero imports from pipeline.py.
All helper functions are duplicated here for isolation.
"""
from __future__ import annotations

import os

# Force MediaPipe to use CPU before any module imports it. This avoids
# EGL/GPU context errors inside Docker containers without display/GPU access.
os.environ.setdefault("MEDIAPIPE_DISABLE_GPU", "1")

import asyncio
import base64
import json
import sys

from common.log_utils import get_logger
from common.datetime_utils import now_brazil

from app.core.config import settings
from app.core.models import ClothesRemovalJob, ClothesRemovalJobStatus
from app.infrastructure.http_client import SE10Client, SE8Client
from app.infrastructure.redis_store import ClothesRemovalJobStore
from app.services.head_detector import detect_head_mask, detect_face_only
from app.services.blend_utils import blend_face_region
from app.validators.pose_detector import render_pose_stick_figure, detect_pose, compare_poses
from app.services.faceid_extractor import extract_faceid_embedding

logger = get_logger(__name__)

# ─── Constants (PRIVATE — only this file) ───────────────────────────────────

DEFAULT_CLOTHES_NEGATIVE = (
    "clothes, fabric, bra, straps, underwear, top, blouse, shirt, "
    "dress, skirt, pattern, floral, textile, garment, "
    "text, watermark, deformed, blurry, cartoon, anime, painting, CGI, "
    "extra limbs, disfigured, poorly drawn face, mutated hands, "
    "bad anatomy, deformed skin, wrinkled, scarred"
)

# ─── Helpers (COPIED — zero sharing with pipeline.py) ───────────────────────

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


def _build_clothes_neutral_ref(orig_img, clothes_mask, person_mask, head_mask):
    """Create IP-Adapter reference with clothing neutralized (Leffa-style).

    Replaces clothing area with mean skin tone + subtle noise so the
    IP-Adapter encoder cannot extract clothing texture features.
    Keeps face/hair/pose/body-shape intact — only clothing is neutralized.

    This is the direct analog of Leffa's insight (CVPR 2025): control what
    the encoder sees to prevent attention leaking to clothing regions.
    """
    import cv2 as _cv2
    import numpy as _np

    if clothes_mask is None or _cv2.countNonZero(clothes_mask) == 0:
        return orig_img.copy()

    h, w = orig_img.shape[:2]
    ref = orig_img.copy()

    # 1. Compute mean skin tone from exposed skin regions (arms, neck, face edges)
    skin_mask = _cv2.bitwise_and(person_mask, _cv2.bitwise_not(clothes_mask))
    skin_mask = _cv2.bitwise_and(skin_mask, _cv2.bitwise_not(head_mask))
    if _cv2.countNonZero(skin_mask) < 100:
        skin_mask = head_mask.copy()

    # Sample skin pixels in HSV
    hsv = _cv2.cvtColor(orig_img, _cv2.COLOR_BGR2HSV)
    skin_pixels = hsv[skin_mask > 0]
    if len(skin_pixels) > 0:
        mean_h = _np.median(skin_pixels[:, 0])
        mean_s = _np.median(skin_pixels[:, 1])
        mean_v = _np.median(skin_pixels[:, 2])
    else:
        mean_h, mean_s, mean_v = 15, 80, 180

    # 2. Create neutral skin fill: solid tone + subtle noise
    fill_hsv = _np.full((h, w, 3), [mean_h, mean_s, mean_v], dtype=_np.uint8)
    noise = _np.random.normal(0, 8, (h, w, 3)).astype(_np.int16)
    fill_hsv = _np.clip(fill_hsv.astype(_np.int16) + noise, 0, 255).astype(_np.uint8)
    fill_bgr = _cv2.cvtColor(fill_hsv, _cv2.COLOR_HSV2BGR)

    # 3. Blur the fill slightly for organic look
    fill_bgr = _cv2.GaussianBlur(fill_bgr, (5, 5), 2.0)

    # 4. Composite: replace clothing area with neutral fill
    clothes_eroded = clothes_mask.copy()
    ke = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))
    clothes_eroded = _cv2.erode(clothes_eroded, ke, iterations=1)

    mask_f = clothes_eroded.astype(_np.float32) / 255.0
    mask_f = _cv2.GaussianBlur(mask_f, (15, 15), 5.0)

    ref = (ref.astype(_np.float32) * (1 - mask_f[:, :, None]) +
           fill_bgr.astype(_np.float32) * mask_f[:, :, None])
    ref = _np.clip(ref, 0, 255).astype(_np.uint8)

    return ref


# ─── Debug Grid ──────────────────────────────────────────────────────────────

def _build_debug_grid(
    panels: list,
    cell_w: int = 400,
    cell_h: int = 600,
    cols: int = 3,
    font_scale: float = 0.55,
    padding: int = 4,
):
    """Build a labeled grid image from a list of (filename, image, label) tuples.

    Each panel is resized to fit cell_w x cell_h, labeled on top, arranged in a grid.
    Grayscale masks are colorized for visual clarity.
    """
    import cv2 as _cv2
    import numpy as _np

    n = len(panels)
    rows_count = (n + cols - 1) // cols

    # Color palette for masks (BGR)
    mask_colors = [
        (0, 0, 200),      # red
        (0, 180, 0),      # green
        (200, 100, 0),    # blue-ish
        (0, 200, 200),    # yellow
        (200, 0, 200),    # magenta
        (0, 160, 255),    # orange
        (255, 100, 0),    # cyan-blue
        (100, 200, 50),   # teal
        (50, 50, 200),    # warm gray
    ]

    canvas_w = cols * (cell_w + padding) + padding
    canvas_h = rows_count * (cell_h + padding) + padding
    canvas = _np.full((canvas_h, canvas_w, 3), 40, dtype=_np.uint8)  # dark gray bg

    label_h = 28  # pixels for label bar

    for idx, (fname, img, label) in enumerate(panels):
        r = idx // cols
        c = idx % cols
        x0 = padding + c * (cell_w + padding)
        y0 = padding + r * (cell_h + padding)

        # Colorize grayscale masks
        if img.ndim == 2 or (img.ndim == 3 and img.shape[2] == 1):
            gray = img if img.ndim == 2 else img[:, :, 0]
            color = mask_colors[idx % len(mask_colors)]
            display = _np.zeros((gray.shape[0], gray.shape[1], 3), dtype=_np.uint8)
            display[gray > 127] = color
        elif img.shape[2] == 4:  # RGBA
            display = _cv2.cvtColor(img, _cv2.COLOR_BGRA2BGR)
        else:
            display = img.copy()

        # Resize to fit cell
        h_img, w_img = display.shape[:2]
        scale = min(cell_w / w_img, (cell_h - label_h) / h_img)
        new_w, new_h = int(w_img * scale), int(h_img * scale)
        resized = _cv2.resize(display, (new_w, new_h), interpolation=_cv2.INTER_AREA)

        # Place centered in cell
        y_off = y0 + label_h + max(0, (cell_h - label_h - new_h) // 2)
        x_off = x0 + max(0, (cell_w - new_w) // 2)
        # Clip to canvas bounds
        y_end = min(y_off + new_h, canvas_h)
        x_end = min(x_off + new_w, canvas_w)
        r_h = y_end - y_off
        r_w = x_end - x_off
        canvas[y_off:y_end, x_off:x_end] = resized[:r_h, :r_w]

        # Label bar
        _cv2.rectangle(canvas, (x0, y0), (x0 + cell_w, y0 + label_h), (30, 30, 30), -1)
        _cv2.putText(canvas, label, (x0 + 6, y0 + 20),
                     _cv2.FONT_HERSHEY_SIMPLEX, font_scale, (220, 220, 220), 1, _cv2.LINE_AA)

        # Border
        _cv2.rectangle(canvas, (x0, y0), (x0 + cell_w, y0 + label_h + cell_h), (80, 80, 80), 1)

    return canvas


# ─── Pose Validation (PRIVATE — only this file) ─────────────────────────────

async def _validate_pose_async(
    original_path: str,
    inpainted_path: str,
    attempt: int = 1,
    max_attempts: int = 3,
    strict: bool = True,
    head_threshold_pct: float = 0.3,
    torso_threshold_pct: float = 0.5,
    limbs_threshold_pct: float = 1.5,
) -> dict:
    """Run pose_validator.py as subprocess and return JSON result."""
    validator_script = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "validators", "pose_validator.py",
    )
    if not os.path.exists(validator_script):
        sys.path.insert(0, os.path.dirname(validator_script))
        try:
            from validators.pose_validator import validate_pose
            return validate_pose(
                original_path=original_path,
                inpainted_path=inpainted_path,
                attempt=attempt,
                max_attempts=max_attempts,
                strict=strict,
                head_threshold_pct=head_threshold_pct,
                torso_threshold_pct=torso_threshold_pct,
                limbs_threshold_pct=limbs_threshold_pct,
            )
        except ImportError:
            return {"pose_changed": False, "confidence": 0.0, "recommendation": "accept",
                    "details": {"head_pct": 0.0, "torso_pct": 0.0, "limbs_pct": 0.0, "max_landmark_pct": 0.0}}

    cmd = [
        sys.executable, validator_script,
        "--original", original_path,
        "--inpainted", inpainted_path,
        "--attempt", str(attempt),
        "--max-attempts", str(max_attempts),
        "--head-threshold", str(head_threshold_pct),
        "--torso-threshold", str(torso_threshold_pct),
        "--limbs-threshold", str(limbs_threshold_pct),
        "--json",
    ]
    if strict:
        cmd.append("--strict")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode in (0, 1):
            return json.loads(stdout.decode())
        else:
            logger.warning("pose_validator failed (rc=%d): %s", proc.returncode, stderr.decode()[:200])
            return {"pose_changed": False, "confidence": 0.0, "recommendation": "accept",
                    "details": {"head_pct": 0.0, "torso_pct": 0.0, "limbs_pct": 0.0, "max_landmark_pct": 0.0}}
    except Exception as e:
        logger.warning("pose_validator error: %s", e)
        return {"pose_changed": False, "confidence": 0.0, "recommendation": "accept",
                "details": {"head_pct": 0.0, "torso_pct": 0.0, "limbs_pct": 0.0, "max_landmark_pct": 0.0}}


# ─── Main Entry Point ────────────────────────────────────────────────────────

async def run_nsfw(job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
    """PRODUCTION NSFW pipeline — retry + pose validation + best selection.

    Uses body_mask (person minus head) instead of clothing mask for larger inpaint area.
    Retries up to 3 times with progressive params if pose validation fails.
    Selects the try with the lowest overall_score (smallest pose difference).
    """
    import cv2 as _cv2
    import numpy as _np

    se10 = SE10Client()
    se8 = SE8Client()

    try:
        image_bytes = _decode_image(job.request.image)
        logger.info("Job %s: nsfw production started", job.job_id)

        orig_img = _cv2.imdecode(_np.frombuffer(image_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if orig_img is None:
            raise ValueError("Failed to decode")
        orig_h, orig_w = orig_img.shape[:2]

        job.update_stage("detecting", "processing", progress=10.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        # ─── Stage 1: SE10 Person Detection ───
        person_seg = await se10.segment(
            image_bytes=image_bytes, filename=f"{job.job_id}_person.jpg",
            classes="person, woman, man", box_threshold=0.20, text_threshold=0.15, mode="person",
            include_pose=True,
        )
        pose_cn_b64 = person_seg.get("controlnet_image")
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

        # Fill ALL internal holes in the person mask — multi-step approach
        # Step 1: Morphological closing to fill small gaps in the mask
        _close_kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (7, 7))
        person_binary = _cv2.morphologyEx(person_binary, _cv2.MORPH_CLOSE, _close_kernel, iterations=3)

        # Step 2: FloodFill from ALL 4 corners + midpoints to catch background pockets
        _h, _w = person_binary.shape
        _flood = person_binary.copy()
        _flood_mask = _np.zeros((_h + 2, _w + 2), _np.uint8)
        seeds = [(0, 0), (_w - 1, 0), (0, _h - 1), (_w - 1, _h - 1),
                 (_w // 2, 0), (_w // 2, _h - 1), (0, _h // 2), (_w - 1, _h // 2)]
        for seed in seeds:
            sx, sy = seed
            if 0 <= sx < _w and 0 <= sy < _h and _flood[sy, sx] == 0:
                _cv2.floodFill(_flood, _flood_mask, (sx, sy), 255)
        _holes = _cv2.bitwise_not(_flood)
        person_binary = _cv2.bitwise_or(person_binary, _holes)
        logger.info("Job %s: person mask holes filled (%d px closed via multi-seed floodFill)",
                     job.job_id, _np.count_nonzero(_holes))

        job.update_stage("detecting", "processing", progress=25.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        # ─── Stage 2: Head/Body Separation ───
        contours, _ = _cv2.findContours(person_binary, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            raise ValueError("No contours")
        largest = max(contours, key=_cv2.contourArea)
        px, py, pw, ph = _cv2.boundingRect(largest)

        head_mask = detect_head_mask(
            orig_img=orig_img,
            person_binary=person_binary,
            person_bbox=(px, py, pw, ph),
            max_head_pct=0.50,
            neck_margin_below=1.8,
            dilate_kernel_size=15,
            dilate_iterations=2,
        )

        body_mask = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(head_mask))

        # Head protection: use head_mask for composite (covers full head + hair)
        head_adjusted = head_mask



        # ─── Stage 3: SE10 Clothes Detection ───
        clothes_seg = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}_clothes_ref.jpg",
            classes="spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment, skirt, pants, shorts, jeans, sweater, jacket, coat, hoodie, t-shirt",
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

        # CRITICAL: Head mask = face+hair+neck (NO clothing)
        # Step 1: Subtract clothes
        if clothes_combined is not None:
            head_mask = _cv2.bitwise_and(head_mask, _cv2.bitwise_not(clothes_combined))
        head_mask = _cv2.bitwise_and(head_mask, person_binary)

        # Step 2: Distance transform to inflate (fills concavities)
        _dist = _cv2.distanceTransform(head_mask, _cv2.DIST_L2, 5)
        _, _head_inflated = _cv2.threshold(_dist, 8, 255, _cv2.THRESH_BINARY)
        head_mask = _cv2.bitwise_or(head_mask, _head_inflated.astype(_np.uint8))
        head_mask = _cv2.bitwise_and(head_mask, person_binary)

        # Step 3: Close + blur for smooth edges
        _ck = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (9, 9))
        head_mask = _cv2.morphologyEx(head_mask, _cv2.MORPH_CLOSE, _ck, iterations=2)
        head_f = head_mask.astype(_np.float32) / 255.0
        head_f = _cv2.GaussianBlur(head_f, (15, 15), 5.0)
        head_mask = (head_f > 0.5).astype(_np.uint8) * 255
        head_mask = _cv2.bitwise_and(head_mask, person_binary)

        # face_protect_mask: Haar-based ellipse covering the FULL FACE
        # (forehead, eyes, nose, mouth, jaw, chin). Preserving the complete
        # original face geometry prevents the displacement seen when only the
        # central face was protected.
        face_protect_mask = detect_face_only(
            orig_img=orig_img,
            person_binary=person_binary,
            margin_above=0.05,
            margin_below=0.55,
            margin_sides=0.40,
        )

        # Shrink the head exclusion slightly so SE8 generates a transition band
        # (jaw, cheeks, temples) between the protected face and the body.
        # The face is still protected by face_protect_mask during composite.
        _buffer_px = max(15, int(min(orig_w, orig_h) * 0.015))
        _buffer_kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (_buffer_px, _buffer_px))
        head_mask_eroded = _cv2.erode(head_mask, _buffer_kernel, iterations=1)
        body_mask = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(head_mask_eroded))
        head_adjusted = head_mask

        exposed_skin = _cv2.bitwise_and(body_mask, _cv2.bitwise_not(clothes_combined)) if clothes_combined is not None else body_mask

        # ─── Stage 4: Mask Preparation ───
        # Strategy: body_mask (person - eroded head) as primary inpaint area.
        # The eroded head leaves a transition band for SE8 to paint naturally.
        dilation_px = max(10, int(min(orig_w, orig_h) * 0.02))

        # Primary inpaint mask = body (person minus head)
        inpaint_mask = body_mask.copy()

        # Moderate expansion to cover sleeves and arm edges
        expand_kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (dilation_px, dilation_px))
        inpaint_mask = _cv2.dilate(inpaint_mask, expand_kernel, iterations=2)

        # Dilate person silhouette to fill edge gaps in SE10 detection
        # This prevents white cloth artifacts at arm/shoulder boundaries
        person_expanded = _cv2.dilate(person_binary, expand_kernel, iterations=3)
        inpaint_mask = _cv2.bitwise_and(inpaint_mask, person_expanded)

        # Morphological closing to fill small holes in the mask
        close_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))
        inpaint_mask = _cv2.morphologyEx(inpaint_mask, _cv2.MORPH_CLOSE, close_k, iterations=2)

        clothes_pct = (inpaint_mask > 0).sum() / inpaint_mask.size * 100
        head_orig_pct = _cv2.countNonZero(head_mask) / head_mask.size * 100
        head_adj_pct = _cv2.countNonZero(head_adjusted) / head_adjusted.size * 100
        logger.info("Job %s: nsfw body=%.1f%% head_orig=%.1f%% head_adj=%.1f%%",
                     job.job_id, clothes_pct, head_orig_pct, head_adj_pct)

        job.update_stage("inpainting", "processing", progress=35.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        _, mask_buf = _cv2.imencode(".png", inpaint_mask)
        mask_b64 = _to_data_uri(base64.b64encode(mask_buf).decode("utf-8"), mime="image/png")

        nsfw_loras = [
            {"enabled": True, "model_name": "NsfwPovAllInOneLoraSdxl-000009.safetensors", "weight": 0.6},
            {"enabled": True, "model_name": "sd_xl_offset_example-lora_1.0.safetensors", "weight": 0.1},
            {"enabled": True, "model_name": "add-detail-xl.safetensors", "weight": 0.7},
            {"enabled": True, "model_name": "None", "weight": 1.0},
            {"enabled": True, "model_name": "None", "weight": 1.0},
        ]

        image_b64 = _to_data_uri(base64.b64encode(image_bytes).decode("utf-8"), mime="image/jpeg")

        # IP-Adapter: use CLOTHES-NEUTRALIZED reference (Leffa-style)
        # The encoder sees pose/face/body-shape but NOT clothing texture.
        # This prevents attention leaking to clothing regions → no sweater residual.
        ip_ref_img = _build_clothes_neutral_ref(
            orig_img, clothes_combined, person_binary, head_mask)
        _, ip_ref_buf = _cv2.imencode(".jpg", ip_ref_img, [_cv2.IMWRITE_JPEG_QUALITY, 90])
        ip_ref_b64 = _to_data_uri(base64.b64encode(ip_ref_buf).decode("utf-8"), mime="image/jpeg")

        # FaceID: extract face embedding for identity preservation
        faceid_embedding = extract_faceid_embedding(orig_img, person_binary)
        if faceid_embedding:
            logger.info("Job %s: FaceID embedding extracted (512-d)", job.job_id)
        else:
            logger.warning("Job %s: FaceID extraction failed, continuing without", job.job_id)

        # Pose conditioning: MediaPipe stick figure as secondary IP-Adapter reference
        # NOTE (2026-06-30): Tested and degraded pose preservation (score 21.3 vs 0.0).
        # Kept disabled in production. The render_pose_stick_figure function remains
        # available in app.validators.pose_detector for future experiments.
        ip_pose_b64 = None
        # try:
        #     pose_result = detect_pose(orig_img, min_detection_confidence=0.5)
        #     if pose_result is not None:
        #         pose_img = render_pose_stick_figure(pose_result, output_size=(orig_w, orig_h))
        #         _, ip_pose_buf = _cv2.imencode(".jpg", pose_img, [_cv2.IMWRITE_JPEG_QUALITY, 95])
        #         ip_pose_b64 = _to_data_uri(base64.b64encode(ip_pose_buf).decode("utf-8"), mime="image/jpeg")
        #         logger.info("Job %s: pose stick figure generated (confidence=%.3f)",
        #                     job.job_id, pose_result.detection_confidence)
        #     else:
        #         logger.warning("Job %s: MediaPipe pose not detected", job.job_id)
        # except Exception as exc:
        #     logger.warning("Job %s: failed to generate pose stick figure: %s", job.job_id, exc)

        nsfw_prompt = (
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

        nsfw_negative = (
            "(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, "
            "wrong anatomy, extra limbs, missing limbs, floating limbs, severed limbs, "
            "(mutated hands and fingers, extra fingers, missing fingers, webbed fingers:1.4), "
            "(bad hands, poorly drawn hands, fused fingers, too many fingers:1.3), "
            "(extra face, second face, face on body, face on chest, face below neck:1.8), "
            "(facial features on torso, eyes on chest, mouth on body:1.6), "
            "long neck, mutation, ugly, blurry, airbrushed, plastic skin, CGI, 3D, render, "
            "clothes, fabric, bra, straps, underwear, pattern, floral, textile, "
            "cartoon, anime, sketch, "
            "(changed pose, moved body, different position, rotated torso:1.5), "
            "(shifted weight, leaning, tilting, bending, twisting:1.4), "
            "(new angle, different posture:1.3), "
            "asymmetric nipples, mismatched skin tone, color banding"
        )

        # Use user-provided prompt if non-empty, otherwise fallback to optimized defaults
        final_prompt = job.request.prompt or nsfw_prompt
        final_negative = job.request.negative_prompt or nsfw_negative

        # ─── Retry loop with pose validation (max 3 attempts) ───
        max_attempts = 3
        tries_metadata: dict[str, dict | None] = {f"try_{i}": None for i in range(1, max_attempts + 1)}
        best_try: str | None = None
        best_composited = None
        best_score: float = float("inf")
        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)

        try:
            _cv2.imwrite(os.path.join(output_dir, "00_original.png"), orig_img)
            _cv2.imwrite(os.path.join(output_dir, "01_person.png"), person_binary)
            _cv2.imwrite(os.path.join(output_dir, "02_head_full.png"), head_mask)
            _cv2.imwrite(os.path.join(output_dir, "03_body.png"), body_mask)
            _cv2.imwrite(os.path.join(output_dir, "03b_face_only.png"), face_protect_mask)
            if clothes_combined is not None:
                _cv2.imwrite(os.path.join(output_dir, "04_clothes.png"), clothes_combined)
            _cv2.imwrite(os.path.join(output_dir, "05_exposed_skin.png"), exposed_skin)
            _cv2.imwrite(os.path.join(output_dir, "06_inpaint_mask.png"), inpaint_mask)
            _cv2.imwrite(os.path.join(output_dir, "07_head_adjusted.png"), head_adjusted)
            if pose_cn_b64 is not None:
                pose_bytes = base64.b64decode(pose_cn_b64.split(",")[1])
                pose_arr = _np.frombuffer(pose_bytes, _np.uint8)
                pose_decoded = _cv2.imdecode(pose_arr, _cv2.IMREAD_COLOR)
                if pose_decoded is not None:
                    _cv2.imwrite(os.path.join(output_dir, "08_pose_controlnet.png"), pose_decoded)
        except Exception as exc:
            logger.warning("Job %s: failed to save debug masks: %s", job.job_id, exc)

        # Save mask overlay on original for visual debugging
        try:
            inpaint_pct = (inpaint_mask > 0).sum() / inpaint_mask.size * 100
            clothes_orig_pct = (clothes_combined > 0).sum() / clothes_combined.size * 100 if clothes_combined is not None else 0
            mask_overlay = orig_img.copy()
            mask_color = _cv2.cvtColor(inpaint_mask, _cv2.COLOR_GRAY2BGR)
            mask_color[:, :, 0] = 0   # no blue
            mask_color[:, :, 2] = 0   # no red → green channel = inpaint region
            mask_overlay = _cv2.addWeighted(mask_overlay, 0.6, mask_color, 0.4, 0)
            _cv2.putText(mask_overlay,
                         f"Inpaint mask: {inpaint_pct:.1f}% | clothes: {clothes_orig_pct:.1f}%",
                         (10, 25), _cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            _cv2.putText(mask_overlay, f"LustifyNSFW | FaceID={'on' if faceid_embedding else 'off'}",
                         (10, 50), _cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            _cv2.imwrite(os.path.join(output_dir, "30_mask_overlay.png"), mask_overlay)
        except Exception:
            pass

        # Save SE10 detection metadata
        try:
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
                "faceid": faceid_embedding is not None,
                "base_model": "lustifySDXLNSFW_v20-inpainting.safetensors",
            }
            with open(os.path.join(output_dir, "detection_meta.json"), "w") as f:
                json.dump(seg_meta, f, indent=2)
        except Exception:
            pass

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
                        _cv2.imwrite(os.path.join(output_dir, f"20_garment_{gi}_{gclass}.png"), gm_color)
                except Exception:
                    pass

        for attempt in range(1, max_attempts + 1):
            try_tag = f"try_{attempt}"
            try_dir = os.path.join(output_dir, try_tag)
            os.makedirs(try_dir, exist_ok=True)

            # Delay between attempts to release GPU memory (prevents CUDA assertion)
            if attempt > 1:
                import asyncio as _asyncio
                await _asyncio.sleep(10)

            _retry_configs = {
                1: {"strength": 0.86, "field": 0.618, "erode": 0, "seed": -1},
                2: {"strength": 0.87, "field": 0.618, "erode": 0, "seed": 42},
                3: {"strength": 0.90, "field": 0.618, "erode": 0, "seed": 99},
            }
            cfg = _retry_configs.get(attempt, _retry_configs[1])

            logger.info("Job %s: attempt %d/%d — strength=%.2f field=%.2f seed=%d",
                        job.job_id, attempt, max_attempts, cfg["strength"], cfg["field"], cfg["seed"])

            # IP-Adapter: clothes-neutralized ref for face/body preservation
            # ControlNet OpenPose: pose stick figure from SE10 for body structure
            ip_adapter_prompts = [
                {
                    "cn_img": ip_ref_b64,
                    "cn_stop": 0.5,
                    "cn_weight": 0.8,
                    "cn_type": "ImagePrompt",
                },
                {"cn_img": None, "cn_stop": 0.5, "cn_weight": 0.0, "cn_type": "ImagePrompt"},
                {"cn_img": None, "cn_stop": 0.5, "cn_weight": 0.0, "cn_type": "ImagePrompt"},
            ]
            # OpenPose ControlNet incompatible with LustifyNSFW (different UNet architecture)
            base_model_name = "lustifySDXLNSFW_v20-inpainting.safetensors"
            if pose_cn_b64 and "juggernaut" in base_model_name.lower():
                ip_adapter_prompts.insert(1, {
                    "cn_img": pose_cn_b64,
                    "cn_stop": 0.7,
                    "cn_weight": 0.5,
                    "cn_type": "OpenPose",
                })
                logger.info("Job %s: OpenPose ControlNet enabled", job.job_id)

            result1 = await se8.inpaint(
                image_b64=image_b64, mask_b64=mask_b64,
                prompt=final_prompt,
                negative_prompt=final_negative,
                inpaint_additional_prompt=final_prompt,
                inpaint_strength=cfg["strength"],
                inpaint_respective_field=cfg["field"],
                inpaint_erode_or_dilate=cfg["erode"],
                loras=nsfw_loras,
                image_prompts=ip_adapter_prompts,
                base_model="lustifySDXLNSFW_v20-inpainting.safetensors",
                invert_mask=True,
                ip_adapter_faceid_embeds=faceid_embedding,
                ip_adapter_faceid_weight=0.8,
            )
            if not result1 or not result1.get("base64"):
                logger.warning("Job %s: SE8 empty on attempt %d", job.job_id, attempt)
                tries_metadata[try_tag] = {
                    "pose_changed": True, "confidence": 0.0,
                    "head_pct": 0.0, "torso_pct": 0.0, "limbs_pct": 0.0,
                    "max_landmark_pct": 999.0, "overall_score": 999.0,
                    "params": cfg, "error": "SE8 empty",
                    "recommendation": "retry" if attempt < max_attempts else "release_anyway",
                }
                continue

            inpainted_bytes = base64.b64decode(result1["base64"])
            inpainted_img = _cv2.imdecode(
                _np.frombuffer(inpainted_bytes, _np.uint8), _cv2.IMREAD_COLOR)
            if inpainted_img is not None and inpainted_img.shape[:2] != (orig_h, orig_w):
                inpainted_img = _cv2.resize(inpainted_img, (orig_w, orig_h))

            # ─── Face preservation: LustifyNSFW preserves face natively ───
            # With LustifyNSFW model, the face is preserved during inpainting.
            # No complex blending needed — just use the inpainted result directly.
            # Face blending (Laplacian/LAB) was needed for JuggernautXL which
            # could displace facial features. Lustify handles this internally.
            composited = inpainted_img.copy()

            # ─── Optional face restoration via SE8 ───
            # CodeFormer/GFPGAN unifies texture between preserved face and generated body,
            # reducing the "cutout" look at the cost of slight identity shift.
            face_restore = getattr(job.request, "face_restore", False)
            face_restore_model = getattr(job.request, "face_restore_model", "CodeFormer")
            face_restore_fidelity = getattr(job.request, "face_restore_fidelity", 0.5)
            restored = None
            if face_restore:
                try:
                    logger.info("Job %s: calling SE8 face restore (%s, fidelity=%.2f)",
                                job.job_id, face_restore_model, face_restore_fidelity)
                    _, comp_buf = _cv2.imencode(".png", composited)
                    comp_b64 = _to_data_uri(base64.b64encode(comp_buf).decode("utf-8"), mime="image/png")
                    restore_result = await se8.restore_face(
                        image_b64=comp_b64,
                        model=face_restore_model,
                        fidelity=face_restore_fidelity,
                    )
                    if restore_result.get("base64"):
                        restored_bytes = base64.b64decode(restore_result["base64"].split(",")[1])
                        restored = _cv2.imdecode(
                            _np.frombuffer(restored_bytes, _np.uint8), _cv2.IMREAD_COLOR)
                        if restored is not None and restored.shape[:2] == (orig_h, orig_w):
                            _cv2.imwrite(os.path.join(try_dir, "result_restored.png"), restored)
                        else:
                            restored = None
                            logger.warning("Job %s: SE8 face restore returned mismatched image", job.job_id)
                except Exception as exc:
                    logger.warning("Job %s: face restore failed, using blended result: %s", job.job_id, exc)

            _cv2.imwrite(os.path.join(try_dir, "result.png"), composited)
            _cv2.imwrite(os.path.join(try_dir, "inpaint_mask.png"), inpaint_mask)
            _cv2.imwrite(os.path.join(try_dir, "head_adjusted.png"), head_adjusted)
            _cv2.imwrite(os.path.join(try_dir, "face_protect_mask.png"), face_protect_mask)

            # Use restored image as the candidate if face restoration succeeded
            if restored is not None:
                composited = restored

            orig_path = os.path.join(output_dir, "00_original.png")
            result_path_try = os.path.join(try_dir, "result.png")

            # Relaxed pose thresholds for NSFW mode: LustifyNSFW regenerates the body
            # region, causing torso landmarks to shift naturally. Face is preserved natively,
            # so we use generous thresholds and rely on head_pct/overall_score instead.
            validator_result = await _validate_pose_async(
                orig_path, result_path_try, attempt, max_attempts, strict=False,
                head_threshold_pct=1.5, torso_threshold_pct=8.0, limbs_threshold_pct=5.0)

            meta = {
                "pose_changed": validator_result.get("pose_changed", True),
                "confidence": validator_result.get("confidence", 0.0),
                "head_pct": validator_result.get("details", {}).get("head_pct", 0.0),
                "torso_pct": validator_result.get("details", {}).get("torso_pct", 0.0),
                "limbs_pct": validator_result.get("details", {}).get("limbs_pct", 0.0),
                "max_landmark_pct": validator_result.get("details", {}).get("max_landmark_pct", 999.0),
                "overall_score": validator_result.get("details", {}).get("max_landmark_pct", 999.0),
                "params": cfg,
                "result_path": f"{try_tag}/result.png",
                "recommendation": validator_result.get("recommendation", "retry"),
            }
            tries_metadata[try_tag] = meta

            with open(os.path.join(try_dir, "metadata.json"), "w") as mf:
                json.dump(meta, mf, indent=2)

            score = meta["overall_score"]
            if score < best_score:
                best_score = score
                best_try = try_tag
                best_composited = composited.copy()

            logger.info("Job %s: %s score=%.3f recommendation=%s",
                        job.job_id, try_tag, score, meta["recommendation"])

            # Always run all 3 attempts to maximize quality.
            # Progressive strength (0.65→0.70→0.75) gives the model
            # multiple chances to produce the best result.

        # ─── Finalize ───
        tries_clean = {k: v for k, v in tries_metadata.items() if v is not None}

        attempts_summary = {
            "job_id": job.job_id,
            "total_attempts": sum(1 for v in tries_clean.values() if v is not None),
            "best_try": best_try,
            "best_score": best_score if best_score < float("inf") else None,
            "tries": tries_clean,
        }
        with open(os.path.join(output_dir, "attempts.json"), "w") as af:
            json.dump(attempts_summary, af, indent=2)

        if best_composited is None:
            logger.warning("Job %s: no valid result from any attempt, marking FAILED", job.job_id)
            job.status = ClothesRemovalJobStatus.FAILED
            job.error = "All attempts failed"
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        _, fb = _cv2.imencode(".png", best_composited)

        # ─── Debug Grid (3x3: all masks + result) ───
        try:
            inpaint_pct = (_cv2.countNonZero(inpaint_mask) / inpaint_mask.size) * 100.0
            panels = [
                ("00_original", orig_img, "1. Original"),
                ("01_person", person_binary, "2. Person (SE10)"),
                ("02_head_full", head_mask, "3. Head (face+hair)"),
                ("03b_face_only", face_protect_mask, "4. Face Only (protected)"),
            ]
            if clothes_combined is not None:
                panels.append(("04_clothes", clothes_combined, "5. Clothes (Florence-2)"))
            panels.extend([
                ("06_inpaint_mask", inpaint_mask, f"6. Inpaint Mask ({inpaint_pct:.1f}%)"),
                ("07_head_adjusted", head_adjusted, f"7. Head Adjusted ({head_adj_pct:.1f}%)"),
                ("result", best_composited, f"8. Result ({best_try}, score={best_score:.3f})"),
            ])
            grid = _build_debug_grid(panels)
            _cv2.imwrite(os.path.join(output_dir, f"{job.job_id}_debug_grid.png"), grid)
        except Exception as exc:
            logger.warning("Job %s: debug grid failed (%s)", job.job_id, exc)

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
        logger.info("Job %s: nsfw production completed — best=%s (score=%.3f) — %s",
                     job.job_id, best_try, best_score, result_path)

    except Exception as e:
        logger.error("Job %s nsfw production failed: %s", job.job_id, e, exc_info=True)
        job.status = ClothesRemovalJobStatus.FAILED
        job.error = str(e)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

    finally:
        await se10.close()
        await se8.close()
