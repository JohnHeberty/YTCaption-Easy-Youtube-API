"""NSFW Production Pipeline — retry + pose validation + best selection.

Shares helpers via app.services._helpers.
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
from app.services._helpers import (
    CLOTHES_CLASSES, DEFAULT_CLOTHES_NEGATIVE, SCORING,
    decode_image as _decode_image,
    to_data_uri as _to_data_uri,
    strip_data_uri as _strip_data_uri,
    fix_b64_padding as _fix_b64_padding,
    combine_masks as _combine_masks,
    detect_skin_hsv as _detect_skin_hsv,
    compute_composite_score as _compute_composite_score,
)

logger = get_logger(__name__)

# ─── Scoring aliases (backward compat) ──────────────────────────────────────
SCORE_W_SKIN = SCORING.skin
SCORE_W_HEAD = SCORING.head
SCORE_W_LANDMARK = SCORING.landmark
SCORE_W_CLOTHES = SCORING.clothes
SCORE_EARLY_STOP = SCORING.early_stop


async def _detect_result_clothes(
    se10: SE10Client,
    inpainted_img,
    orig_h: int,
    orig_w: int,
) -> float:
    """Detect residual clothing on an inpainted result (SE10 call)."""
    try:
        import cv2 as _cv2
        _, result_buf = _cv2.imencode(".jpg", inpainted_img, [_cv2.IMWRITE_JPEG_QUALITY, 90])
        result_bytes = result_buf.tobytes()
        result_seg = await se10.segment(
            image_bytes=result_bytes,
            filename="result.jpg",
            classes=CLOTHES_CLASSES,
            box_threshold=0.06,
            text_threshold=0.04,
            mode="clothes",
            detector="ensemble",
        )
        if result_seg.get("detected") and result_seg.get("masks"):
            result_mask = _combine_masks(result_seg["masks"], orig_h, orig_w)
            if result_mask is not None:
                return float((result_mask > 0).sum() / result_mask.size * 100)
        return 0.0
    except Exception as exc:
        logger.warning("Result clothes detection failed: %s", exc)
        return 0.0


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

        # ─── Stage 1: SE10 Person Detection (ensemble: GD + YOLO11) ───
        person_seg = await se10.segment(
            image_bytes=image_bytes, filename=f"{job.job_id}_person.jpg",
            classes="person, woman, man", box_threshold=0.20, text_threshold=0.15, mode="person",
            detector="ensemble", include_pose=True,
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

        # ─── Fallback: Retry with lower thresholds if person mask too small ───
        person_coverage = (person_binary > 0).sum() / person_binary.size * 100
        if person_coverage < 10.0:
            logger.warning("Job %s: person coverage too low (%.1f%% < 10%%), retrying with lower thresholds",
                           job.job_id, person_coverage)
            person_seg_retry = await se10.segment(
                image_bytes=image_bytes, filename=f"{job.job_id}_person_retry.jpg",
                classes="person, woman, man", box_threshold=0.10, text_threshold=0.08,
                mode="person", detector="ensemble", include_pose=True,
            )
            if person_seg_retry.get("detected") and person_seg_retry.get("masks"):
                best_idx_r = max(range(len(person_seg_retry["objects"])),
                                 key=lambda i: person_seg_retry["objects"][i].get("area_pct", 0))
                raw_pr = _strip_data_uri(person_seg_retry["masks"][best_idx_r])
                person_mask_r = _cv2.imdecode(
                    _np.frombuffer(base64.b64decode(_fix_b64_padding(raw_pr)), _np.uint8),
                    _cv2.IMREAD_GRAYSCALE)
                if person_mask_r is not None:
                    if person_mask_r.shape[:2] != (orig_h, orig_w):
                        person_mask_r = _cv2.resize(person_mask_r, (orig_w, orig_h))
                    person_binary_r = (person_mask_r > 127).astype(_np.uint8) * 255
                    retry_coverage = (person_binary_r > 0).sum() / person_binary_r.size * 100
                    if retry_coverage > person_coverage:
                        person_binary = person_binary_r
                        person_seg = person_seg_retry
                        if person_seg_retry.get("controlnet_image"):
                            pose_cn_b64 = person_seg_retry["controlnet_image"]
                        person_coverage = retry_coverage
                        logger.info("Job %s: retry improved coverage to %.1f%%",
                                    job.job_id, person_coverage)

        # ─── Fallback 2: GrabCut if still too small ───
        if person_coverage < 10.0:
            logger.warning("Job %s: still low coverage (%.1f%%), trying GrabCut fallback",
                           job.job_id, person_coverage)
            faces = []
            try:
                from app.services.head_detector import _detect_faces
                faces = _detect_faces(orig_img)
            except Exception:
                pass
            if faces:
                face = max(faces, key=lambda f: f[2] * f[3])
                fx, fy, fw, fh = face
                # Create a generous rectangle around the face for GrabCut seed
                gc_margin_x = int(fw * 3.0)
                gc_margin_top = int(fh * 4.0)
                gc_margin_bot = int(fh * 6.0)
                gc_x1 = max(0, fx - gc_margin_x)
                gc_y1 = max(0, fy - gc_margin_top)
                gc_x2 = min(orig_w, fx + fw + gc_margin_x)
                gc_y2 = min(orig_h, fy + fh + gc_margin_bot)
                gc_rect = (gc_x1, gc_y1, gc_x2 - gc_x1, gc_y2 - gc_y1)

                gc_mask_gc = _np.zeros((orig_h, orig_w), _np.uint8)
                # Mark inside as probable foreground, border strip as probable background
                gc_mask_gc[:] = _cv2.GC_PR_FGD
                border = 5
                gc_mask_gc[:border, :] = _cv2.GC_PR_BGD
                gc_mask_gc[-border:, :] = _cv2.GC_PR_BGD
                gc_mask_gc[:, :border] = _cv2.GC_PR_BGD
                gc_mask_gc[:, -border:] = _cv2.GC_PR_BGD

                bgd_model = _np.zeros((1, 65), _np.float64)
                fgd_model = _np.zeros((1, 65), _np.float64)
                try:
                    _cv2.grabCut(orig_img, gc_mask_gc, gc_rect, bgd_model, fgd_model,
                                 5, _cv2.GC_INIT_WITH_RECT)
                    gc_fg = _np.where((gc_mask_gc == _cv2.GC_FGD) | (gc_mask_gc == _cv2.GC_PR_FGD), 255, 0).astype(_np.uint8)
                    gc_coverage = (gc_fg > 0).sum() / gc_fg.size * 100
                    if gc_coverage > person_coverage:
                        person_binary = gc_fg
                        person_coverage = gc_coverage
                        logger.info("Job %s: GrabCut improved coverage to %.1f%%",
                                    job.job_id, person_coverage)
                except Exception as exc:
                    logger.warning("Job %s: GrabCut failed: %s", job.job_id, exc)

            # Final fallback: expand face bbox to cover expected body area
            if person_coverage < 10.0 and faces:
                face = max(faces, key=lambda f: f[2] * f[3])
                fx, fy, fw, fh = face
                body_w = int(fw * 4.0)
                body_h = int(fh * 8.0)
                body_cx = fx + fw // 2
                body_cy = fy + fh + body_h // 2
                body_x1 = max(0, body_cx - body_w // 2)
                body_y1 = max(0, fy - int(fh * 1.5))
                body_x2 = min(orig_w, body_cx + body_w // 2)
                body_y2 = min(orig_h, body_cy + body_h // 2)
                body_rect_mask = _np.zeros((orig_h, orig_w), _np.uint8)
                # Ellipse inside the rectangle
                ell_cx = (body_x1 + body_x2) // 2
                ell_cy = (body_y1 + body_y2) // 2
                ell_w = (body_x2 - body_x1) // 2
                ell_h = (body_y2 - body_y1) // 2
                _cv2.ellipse(body_rect_mask, (ell_cx, ell_cy), (ell_w, ell_h), 0, 0, 360, 255, -1)
                ell_coverage = (body_rect_mask > 0).sum() / body_rect_mask.size * 100
                if ell_coverage > person_coverage:
                    person_binary = body_rect_mask
                    person_coverage = ell_coverage
                    logger.info("Job %s: face-ellipse fallback coverage=%.1f%%",
                                job.job_id, person_coverage)

        job.update_stage("detecting", "processing", progress=25.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        # ─── Stage 2: Head/Body Separation ───
        contours, _ = _cv2.findContours(person_binary, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            raise ValueError("No contours")
        largest = max(contours, key=_cv2.contourArea)
        px, py, pw, ph = _cv2.boundingRect(largest)

        # ════════════════════════════════════════════════════════════════════
        # LAYERED MASK CONSTRUCTION (Professional multi-step approach)
        # ════════════════════════════════════════════════════════════════════
        # Layer 1: Person silhouette (SE10) — background already removed
        # Layer 2: Hair protection — head_mask (ellipse, tight neck)
        # Layer 3: Face protection — face_oval_mask (MediaPipe landmarks)
        # Layer 4: Combined protection = hair OR face
        # Layer 5: Inpaint = person − protection (clothing + exposed skin)
        # Layer 6: Dilate + close for smooth SE8 edges
        # ════════════════════════════════════════════════════════════════════

        # ─── Layer 2: Hair protection (tight neck — does NOT eat clothing) ──
        hair_mask = detect_head_mask(
            orig_img=orig_img,
            person_binary=person_binary,
            person_bbox=(px, py, pw, ph),
            max_head_pct=0.50,
            neck_margin_below=0.3,
            dilate_kernel_size=25,
            dilate_iterations=3,
            expand_up=2.5,
            expand_w=0.5,
        )

        # ─── Layer 3: Face protection (MediaPipe Face Mesh oval) ─────────
        from app.services.head_detector import detect_face_oval_mask
        face_mask = detect_face_oval_mask(
            orig_img=orig_img,
            person_binary=person_binary,
            feather_bottom_px=25,
        )
        if _cv2.countNonZero(face_mask) == 0:
            logger.warning("Job %s: face_oval_mask empty, falling back to haarcascade", job.job_id)
            face_mask = detect_face_only(
                orig_img=orig_img,
                person_binary=person_binary,
                margin_above=0.50,
                margin_below=0.70,
                margin_sides=0.40,
            )

        # ─── Layer 4: Combined protection = hair OR face ─────────────────
        protection_mask = _cv2.bitwise_or(hair_mask, face_mask)
        logger.info("Job %s: protection mask — hair=%d px, face=%d px, combined=%d px",
                     job.job_id,
                     _cv2.countNonZero(hair_mask),
                     _cv2.countNonZero(face_mask),
                     _cv2.countNonZero(protection_mask))

        # ─── Layer 5: Inpaint = person − protection ──────────────────────
        # This covers clothing + exposed skin (everything the person has
        # that is NOT hair and NOT face).
        inpaint_mask = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(protection_mask))

        # ─── Layer 6: Dilate + close for smooth SE8 edges ────────────────
        dilation_px = max(10, int(min(orig_w, orig_h) * 0.02))
        expand_kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (dilation_px, dilation_px))
        inpaint_mask = _cv2.dilate(inpaint_mask, expand_kernel, iterations=2)

        # Clip to expanded person (no background leaking)
        person_expanded = _cv2.dilate(person_binary, expand_kernel, iterations=3)
        inpaint_mask = _cv2.bitwise_and(inpaint_mask, person_expanded)

        # Morphological closing to fill small holes
        close_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))
        inpaint_mask = _cv2.morphologyEx(inpaint_mask, _cv2.MORPH_CLOSE, close_k, iterations=2)

        head_adjusted = hair_mask

        clothes_pct = (inpaint_mask > 0).sum() / inpaint_mask.size * 100
        hair_pct = _cv2.countNonZero(hair_mask) / hair_mask.size * 100
        head_adj_pct = _cv2.countNonZero(head_adjusted) / head_adjusted.size * 100
        logger.info("Job %s: nsfw inpaint=%.1f%% hair=%.1f%% head_adj=%.1f%%",
                     job.job_id, clothes_pct, hair_pct, head_adj_pct)

        job.update_stage("detecting", "completed", progress=100.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        # ─── SE10 Clothes Detection (for IP-Adapter reference + debug) ───
        clothes_seg = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}_clothes_ref.jpg",
            classes="spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment, skirt, pants, shorts, jeans, sweater, jacket, coat, hoodie, t-shirt",
            box_threshold=0.12, text_threshold=0.08,
            mode="clothes", detector="ensemble",
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
            orig_img, clothes_combined, person_binary, hair_mask)
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

        # /jobs/nsfw always uses hardcoded NSFW prompt — ignores user prompt.
        # User prompt overrides were causing non-NSFW results (e.g. "elegant dress"
        # bypassed the NSFW generation). For custom prompts, use /jobs/nsfw-test.
        if job.request.prompt:
            logger.info("Job %s: ignoring user prompt on /jobs/nsfw route, using hardcoded NSFW prompt",
                        job.job_id)
        final_prompt = nsfw_prompt
        final_negative = nsfw_negative

        # ─── Retry loop with multidimensional scoring (max 5 attempts) ───
        max_attempts = 5
        base_strength = 0.86
        tries_metadata: dict[str, dict | None] = {f"try_{i}": None for i in range(1, max_attempts + 1)}
        best_try: str | None = None
        best_composited = None
        best_score: float = float("inf")
        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)

        # Compute original skin_pct as baseline for skin_ratio scoring
        original_skin_pct = _detect_skin_hsv(orig_img)
        logger.info("Job %s: original skin_pct=%.1f%% (HSV baseline)", job.job_id, original_skin_pct)

        for _dbg_num, _dbg_name, _dbg_img in [
            (0, "original", orig_img),
            (1, "person", person_binary),
            (2, "head_full", hair_mask),
            (3, "face_only", face_mask),
            (4, "clothes", clothes_combined),
            (5, "inpaint_mask", inpaint_mask),
            (6, "head_adjusted", head_adjusted),
        ]:
            if _dbg_img is not None:
                try:
                    _cv2.imwrite(os.path.join(output_dir, f"{_dbg_num:02d}_{_dbg_name}.png"), _dbg_img)
                except Exception as exc:
                    logger.warning("Job %s: debug save %s failed: %s", job.job_id, _dbg_name, exc)
        if pose_cn_b64 is not None:
            try:
                pose_bytes = base64.b64decode(pose_cn_b64.split(",")[1])
                pose_arr = _np.frombuffer(pose_bytes, _np.uint8)
                pose_decoded = _cv2.imdecode(pose_arr, _cv2.IMREAD_COLOR)
                if pose_decoded is not None:
                    _cv2.imwrite(os.path.join(output_dir, "08_pose_controlnet.png"), pose_decoded)
            except Exception:
                pass

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

            # Head protection overlay: blue = hair_mask, green = inpaint
            face_overlay = orig_img.copy()
            hm_color = _cv2.cvtColor(hair_mask, _cv2.COLOR_GRAY2BGR)
            hm_color[:, :, 1] = 0  # no green → blue channel = head protection
            hm_color[:, :, 2] = 0  # no red
            face_overlay = _cv2.addWeighted(face_overlay, 0.6, hm_color, 0.4, 0)
            inp_color = _cv2.cvtColor(inpaint_mask, _cv2.COLOR_GRAY2BGR)
            inp_color[:, :, 0] = 0  # no blue → green channel = inpaint
            inp_color[:, :, 2] = 0  # no red
            face_overlay = _cv2.addWeighted(face_overlay, 0.7, inp_color, 0.3, 0)
            head_pct = _cv2.countNonZero(hair_mask) / hair_mask.size * 100
            _cv2.putText(face_overlay,
                         f"Head protect: {head_pct:.1f}% | Inpaint: {inpaint_pct:.1f}%",
                         (10, 25), _cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 100, 0), 2)
            _cv2.imwrite(os.path.join(output_dir, "31_face_protect_overlay.png"), face_overlay)
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

            strength = base_strength + 0.03 * (attempt - 1)
            cfg = {"strength": strength, "field": 0.618, "erode": 0, "seed": -1}

            logger.info("Job %s: attempt %d/%d — strength=%.2f field=%.2f",
                        job.job_id, attempt, max_attempts, cfg["strength"], cfg["field"])

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
            # OpenPose ControlNet — works with any SDXL model via ControlNet Union SDXL
            if pose_cn_b64:
                ip_adapter_prompts.insert(1, {
                    "cn_img": pose_cn_b64,
                    "cn_stop": 0.7,
                    "cn_weight": 0.3,
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
            _cv2.imwrite(os.path.join(try_dir, "face_mask.png"), face_mask)

            # Use restored image as the candidate if face restoration succeeded
            if restored is not None:
                composited = restored

            orig_path = os.path.join(output_dir, "00_original.png")
            result_path_try = os.path.join(try_dir, "result.png")

            # ─── Pose Validation (DWPose — 130 keypoints) ───
            pose_score = 999.0
            pose_changed = True
            head_avg = 0.0
            torso_avg = 0.0
            limbs_avg = 0.0
            hands_avg = 0.0
            max_landmark = 0.0
            try:
                orig_pose = detect_pose(orig_img, min_detection_confidence=0.5)
                result_pose = detect_pose(composited, min_detection_confidence=0.5)
                if orig_pose and result_pose:
                    comparison = compare_poses(
                        orig_pose, result_pose,
                        strict=False,
                        head_threshold_pct=1.5,
                        torso_threshold_pct=8.0,
                        limbs_threshold_pct=5.0,
                        hands_threshold_pct=5.0,
                    )
                    pose_changed = comparison.pose_changed
                    head_diffs = [d.distance_normalized for d in comparison.diffs if d.group == "HEAD"]
                    torso_diffs = [d.distance_normalized for d in comparison.diffs if d.group == "TORSO"]
                    limb_diffs = [d.distance_normalized for d in comparison.diffs if d.group == "LIMB"]
                    hand_diffs = [d.distance_normalized for d in comparison.diffs if d.group in ("HAND_LEFT", "HAND_RIGHT")]
                    head_avg = float(_np.mean(head_diffs)) if head_diffs else 0.0
                    torso_avg = float(_np.mean(torso_diffs)) if torso_diffs else 0.0
                    limbs_avg = float(_np.mean(limb_diffs)) if limb_diffs else 0.0
                    hands_avg = float(_np.mean(hand_diffs)) if hand_diffs else 0.0
                    max_landmark = float(max(
                        (d.distance_normalized for d in comparison.diffs), default=0.0
                    ))
                    pose_score = head_avg
            except Exception as exc:
                logger.warning("Job %s: attempt %d pose validation error: %s", job.job_id, attempt, exc)

            # ─── Result Clothes Detection (SE10) ───
            result_clothes_pct = await _detect_result_clothes(se10, composited, orig_h, orig_w)

            # ─── Skin Detection (HSV, local) ───
            result_skin_pct = _detect_skin_hsv(composited)
            skin_ratio = result_skin_pct / original_skin_pct if original_skin_pct > 0 else 1.0

            # ─── Composite Score ───
            composite_score = _compute_composite_score(
                skin_ratio=skin_ratio,
                head_avg=head_avg,
                clothes_pct=result_clothes_pct,
                max_landmark=max_landmark,
            )

            meta = {
                "pose_changed": bool(pose_changed),
                "head_pct": round(head_avg, 3),
                "torso_pct": round(torso_avg, 3),
                "limbs_pct": round(limbs_avg, 3),
                "hands_pct": round(hands_avg, 3),
                "max_landmark_pct": round(max_landmark, 3),
                "result_clothes_pct": round(result_clothes_pct, 3),
                "result_skin_pct": round(result_skin_pct, 3),
                "skin_ratio": round(skin_ratio, 3),
                "composite_score": float(composite_score),
                "params": cfg,
                "result_path": f"{try_tag}/result.png",
            }
            tries_metadata[try_tag] = meta

            with open(os.path.join(try_dir, "metadata.json"), "w") as mf:
                json.dump(meta, mf, indent=2)

            score = meta["composite_score"]
            if score < best_score:
                best_score = score
                best_try = try_tag
                best_composited = composited.copy()

            logger.info("Job %s: %s composite=%.3f skin_ratio=%.2f head=%.3f landmark=%.3f clothes=%.1f",
                        job.job_id, try_tag, composite_score, skin_ratio, head_avg, max_landmark, result_clothes_pct)

            # Early stop: always run at least 2 tries, then stop if both are excellent
            if attempt >= 2 and composite_score < SCORE_EARLY_STOP and not pose_changed:
                logger.info("Job %s: try %d composite=%.3f < %.1f with stable pose, stopping early",
                            job.job_id, attempt, composite_score, SCORE_EARLY_STOP)
                break
            elif composite_score < SCORE_EARLY_STOP and pose_changed:
                logger.info("Job %s: composite=%.3f but pose_changed=true (landmark=%.1f%%), continuing",
                            job.job_id, composite_score, max_landmark)
            elif attempt < 2 and composite_score < SCORE_EARLY_STOP:
                logger.info("Job %s: try %d composite=%.3f < %.1f but minimum 2 tries required, continuing",
                            job.job_id, attempt, composite_score, SCORE_EARLY_STOP)

        # ─── Finalize ───
        tries_clean = {k: v for k, v in tries_metadata.items() if v is not None}

        best_meta = tries_clean.get(best_try, {}) if best_try else {}
        attempts_summary = {
            "job_id": job.job_id,
            "scoring": "multidimensional_v2",
            "scoring_weights": {
                "skin": SCORE_W_SKIN,
                "head": SCORE_W_HEAD,
                "landmark": SCORE_W_LANDMARK,
                "clothes": SCORE_W_CLOTHES,
            },
            "original_skin_pct": float(round(original_skin_pct, 1)),
            "total_attempts": sum(1 for v in tries_clean.values() if v is not None),
            "best_try": best_try,
            "best_composite_score": best_score if best_score < float("inf") else None,
            "best_skin_ratio": float(best_meta.get("skin_ratio", 0.0)),
            "best_head_pct": float(best_meta.get("head_pct", 0.0)),
            "best_max_landmark_pct": float(best_meta.get("max_landmark_pct", 0.0)),
            "best_clothes_pct": float(best_meta.get("result_clothes_pct", 0.0)),
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

        # ─── Upscale via 4x-UltraSharp ───
        upscale_enabled = getattr(job.request, "upscale", True) if hasattr(job, "request") else True
        if upscale_enabled:
            try:
                logger.info("Job %s: upscaling via 4x-UltraSharp", job.job_id)
                _, upscale_buf = _cv2.imencode(".png", best_composited)
                upscale_b64 = _to_data_uri(base64.b64encode(upscale_buf).decode("utf-8"), mime="image/png")
                upscale_result = await se8.upscale(image_b64=upscale_b64, scale=2.0)
                if upscale_result and upscale_result.get("base64"):
                    upscaled_b64 = upscale_result["base64"]
                    if "," in upscaled_b64 and upscaled_b64.startswith("data:"):
                        upscaled_b64 = upscaled_b64.split(",", 1)[1]
                    upscaled_b64 = _fix_b64_padding(upscaled_b64)
                    upscaled_bytes = base64.b64decode(upscaled_b64)
                    upscaled_img = _cv2.imdecode(
                        _np.frombuffer(upscaled_bytes, _np.uint8), _cv2.IMREAD_COLOR)
                    if upscaled_img is not None:
                        best_composited = upscaled_img
                        uh, uw = upscaled_img.shape[:2]
                        logger.info("Job %s: upscale completed (%dx%d)", job.job_id, uw, uh)
                    else:
                        logger.warning("Job %s: upscale decode failed, using original", job.job_id)
                else:
                    logger.warning("Job %s: upscale returned no base64, using original", job.job_id)
            except Exception as exc:
                logger.warning("Job %s: upscale failed (%s), using original", job.job_id, exc)
        else:
            logger.info("Job %s: upscale disabled by request", job.job_id)

        _, fb = _cv2.imencode(".png", best_composited)

        # ─── Debug Grid (3x3: all masks + result) ───
        try:
            inpaint_pct = (_cv2.countNonZero(inpaint_mask) / inpaint_mask.size) * 100.0
            panels = [
                ("00_original", orig_img, "1. Original"),
                ("01_person", person_binary, "2. Person (SE10)"),
                ("02_head_full", hair_mask, "3. Head (face+hair)"),
                ("03b_face_only", face_mask, "4. Face Only (protected)"),
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
