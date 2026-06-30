"""NSFW Production Pipeline — retry + pose validation + best selection.

This is a COMPLETELY INDEPENDENT file. Zero imports from pipeline.py.
All helper functions are duplicated here for isolation.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys

from common.log_utils import get_logger
from common.datetime_utils import now_brazil

from app.core.config import settings
from app.core.models import ClothesRemovalJob, ClothesRemovalJobStatus
from app.infrastructure.http_client import SE10Client, SE8Client
from app.infrastructure.redis_store import ClothesRemovalJobStore
from app.services.head_detector import detect_head_mask, detect_face_only

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
            neck_margin_below=1.2,
            dilate_kernel_size=15,
            dilate_iterations=2,
        )

        body_mask = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(head_mask))

        # Head protection: use head_mask for composite (covers full head + hair)
        head_adjusted = head_mask

        # face_protect_mask: larger ellipse for better face protection
        face_protect_mask = detect_face_only(
            orig_img=orig_img,
            person_binary=person_binary,
            margin_above=0.50,
            margin_below=0.70,
            margin_sides=0.40,
        )

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

        body_mask = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(head_mask))
        head_adjusted = head_mask

        exposed_skin = _cv2.bitwise_and(body_mask, _cv2.bitwise_not(clothes_combined)) if clothes_combined is not None else body_mask

        # ─── Stage 4: Mask Preparation ───
        # Strategy: body_mask (person - head) as primary inpaint area
        # NO face buffer — the face paste in composite handles protection
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

        # Create face-masked version for IP-Adapter reference
        # This prevents the model from injecting face features into the body area
        # IP-Adapter gets: proportions, skin tone, composition — NOT the face
        ip_ref_img = orig_img.copy()
        # Fill face region with median skin color — total face removal
        face_cover = _cv2.dilate(head_mask,
                                  _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (30, 30)),
                                  iterations=3)
        face_cover = _cv2.bitwise_or(face_cover, face_protect_mask)
        # Sample median color from exposed skin area (arms/torso)
        skin_mask = _cv2.inRange(_cv2.cvtColor(orig_img, _cv2.COLOR_BGR2HSV),
                                 _np.array([0, 20, 80]), _np.array([25, 150, 255]))
        skin_mask = _cv2.bitwise_and(skin_mask, person_binary)
        skin_mask = _cv2.bitwise_and(skin_mask, _cv2.bitwise_not(face_cover))
        skin_pixels = orig_img[skin_mask > 0]
        if len(skin_pixels) > 0:
            median_color = _np.median(skin_pixels, axis=0).astype(_np.uint8)
        else:
            median_color = _np.array([180, 160, 140], dtype=_np.uint8)
        # Soft fill: blend face area toward median color with gradient
        face_float = face_cover.astype(_np.float32) / 255.0
        face_blend = _cv2.GaussianBlur(face_float, (31, 31), 10)
        for c in range(3):
            ip_ref_img[:, :, c] = (ip_ref_img[:, :, c].astype(_np.float32) * (1 - face_blend) +
                                    float(median_color[c]) * face_blend).astype(_np.uint8)
        _, ip_ref_buf = _cv2.imencode(".jpg", ip_ref_img, [_cv2.IMWRITE_JPEG_QUALITY, 90])
        ip_ref_b64 = _to_data_uri(base64.b64encode(ip_ref_buf).decode("utf-8"), mime="image/jpeg")

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
        except Exception as exc:
            logger.warning("Job %s: failed to save debug masks: %s", job.job_id, exc)

        for attempt in range(1, max_attempts + 1):
            try_tag = f"try_{attempt}"
            try_dir = os.path.join(output_dir, try_tag)
            os.makedirs(try_dir, exist_ok=True)

            # Delay between attempts to release GPU memory (prevents CUDA assertion)
            if attempt > 1:
                import asyncio as _asyncio
                await _asyncio.sleep(10)

            _retry_configs = {
                1: {"strength": 0.85, "field": 0.618, "erode": 0, "seed": -1},
                2: {"strength": 0.90, "field": 0.618, "erode": 0, "seed": 42},
                3: {"strength": 1.00, "field": 0.618, "erode": 0, "seed": 99},
            }
            cfg = _retry_configs.get(attempt, _retry_configs[1])

            logger.info("Job %s: attempt %d/%d — strength=%.2f field=%.2f seed=%d",
                        job.job_id, attempt, max_attempts, cfg["strength"], cfg["field"], cfg["seed"])

            # IP-Adapter: pass face-masked image as reference
            # Proportions, skin tone, composition preserved — face excluded
            ip_adapter_prompts = [
                {
                    "cn_img": ip_ref_b64,
                    "cn_stop": 0.3,
                    "cn_weight": 0.35,
                    "cn_type": "ImagePrompt",
                },
                {"cn_img": None, "cn_stop": 0.5, "cn_weight": 0.0, "cn_type": "ImagePrompt"},
                {"cn_img": None, "cn_stop": 0.5, "cn_weight": 0.0, "cn_type": "ImagePrompt"},
                {"cn_img": None, "cn_stop": 0.5, "cn_weight": 0.0, "cn_type": "ImagePrompt"},
            ]

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
                base_model="juggernautXL_v8Rundiffusion.safetensors",
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

            inpainted_img[head_adjusted > 0] = orig_img[head_adjusted > 0]

            # Simple composite: paste original face over inpainted result
            composited = inpainted_img.copy()
            composited[head_adjusted > 0] = orig_img[head_adjusted > 0]

            _cv2.imwrite(os.path.join(try_dir, "result.png"), composited)
            _cv2.imwrite(os.path.join(try_dir, "inpaint_mask.png"), inpaint_mask)
            _cv2.imwrite(os.path.join(try_dir, "head_adjusted.png"), head_adjusted)

            orig_path = os.path.join(output_dir, "00_original.png")
            result_path_try = os.path.join(try_dir, "result.png")
            validator_result = await _validate_pose_async(
                orig_path, result_path_try, attempt, max_attempts, strict=True)

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
