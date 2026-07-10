"""Person detection with fallback strategies."""
from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as _np

from .image_utils import strip_data_uri, fix_b64_padding

logger = logging.getLogger(__name__)


async def detect_person_with_fallbacks(
    se10,
    image_bytes: bytes,
    job_id: str,
    orig_h: int,
    orig_w: int,
    include_pose: bool = True,
) -> tuple["_np.ndarray | None", dict | None, str | None]:
    """Detect person mask with 3 fallback strategies.

    Returns (person_binary, person_seg, pose_cn_b64) or (None, None, None) if no person.
    """
    import cv2 as _cv2
    import numpy as _np

    # Primary detection
    person_seg = await se10.segment(
        image_bytes=image_bytes, filename=f"{job_id}_person.jpg",
        classes="person, woman, man", box_threshold=0.20, text_threshold=0.15,
        mode="person", detector="ensemble", include_pose=include_pose,
    )
    pose_cn_b64 = person_seg.get("controlnet_image") if include_pose else None

    if not person_seg.get("detected") or not person_seg.get("masks"):
        return None, None, None

    best_idx = max(range(len(person_seg["objects"])),
                   key=lambda i: person_seg["objects"][i].get("area_pct", 0))
    raw_p = strip_data_uri(person_seg["masks"][best_idx])
    person_mask = _cv2.imdecode(
        _np.frombuffer(base64.b64decode(fix_b64_padding(raw_p)), _np.uint8),
        _cv2.IMREAD_GRAYSCALE)
    if person_mask is None:
        return None, None, None
    if person_mask.shape[:2] != (orig_h, orig_w):
        person_mask = _cv2.resize(person_mask, (orig_w, orig_h))
    person_binary = (person_mask > 127).astype(_np.uint8) * 255

    # Fill ALL internal holes
    close_kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (7, 7))
    person_binary = _cv2.morphologyEx(person_binary, _cv2.MORPH_CLOSE, close_kernel, iterations=3)

    # FloodFill from ALL 4 corners + midpoints
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

    person_coverage = (person_binary > 0).sum() / person_binary.size * 100

    # Fallback 1: Retry with lower thresholds
    if person_coverage < 10.0:
        logger.warning("Job %s: person coverage %.1f%% < 10%%, retrying with lower thresholds",
                       job_id, person_coverage)
        person_seg_retry = await se10.segment(
            image_bytes=image_bytes, filename=f"{job_id}_person_retry.jpg",
            classes="person, woman, man", box_threshold=0.10, text_threshold=0.08,
            mode="person", detector="ensemble", include_pose=include_pose,
        )
        if person_seg_retry.get("detected") and person_seg_retry.get("masks"):
            best_idx_r = max(range(len(person_seg_retry["objects"])),
                             key=lambda i: person_seg_retry["objects"][i].get("area_pct", 0))
            raw_pr = strip_data_uri(person_seg_retry["masks"][best_idx_r])
            person_mask_r = _cv2.imdecode(
                _np.frombuffer(base64.b64decode(fix_b64_padding(raw_pr)), _np.uint8),
                _cv2.IMREAD_GRAYSCALE)
            if person_mask_r is not None:
                if person_mask_r.shape[:2] != (orig_h, orig_w):
                    person_mask_r = _cv2.resize(person_mask_r, (orig_w, orig_h))
                person_binary_r = (person_mask_r > 127).astype(_np.uint8) * 255
                retry_coverage = (person_binary_r > 0).sum() / person_binary_r.size * 100
                if retry_coverage > person_coverage:
                    person_binary = person_binary_r
                    person_seg = person_seg_retry
                    if include_pose and person_seg_retry.get("controlnet_image"):
                        pose_cn_b64 = person_seg_retry["controlnet_image"]
                    person_coverage = retry_coverage

    # Fallback 2: GrabCut
    if person_coverage < 10.0:
        logger.warning("Job %s: still low coverage %.1f%%, trying GrabCut", job_id, person_coverage)
        person_binary = _grabcut_fallback(person_binary, orig_h, orig_w)
        person_coverage = (person_binary > 0).sum() / person_binary.size * 100

    # Fallback 3: Face-ellipse
    if person_coverage < 10.0:
        logger.warning("Job %s: still low coverage %.1f%%, trying face-ellipse", job_id, person_coverage)
        person_binary = _face_ellipse_fallback(orig_h, orig_w)
        person_coverage = (person_binary > 0).sum() / person_binary.size * 100

    return person_binary, person_seg, pose_cn_b64


def _grabcut_fallback(person_binary: "_np.ndarray", orig_h: int, orig_w: int) -> "_np.ndarray":
    """GrabCut fallback for person detection."""
    import cv2 as _cv2
    import numpy as _np

    try:
        from app.services.head_detector import _detect_faces
        faces = _detect_faces(_np.zeros((orig_h, orig_w, 3), _np.uint8))
    except Exception:
        faces = []

    if not faces:
        return person_binary

    face = max(faces, key=lambda f: f[2] * f[3])
    fx, fy, fw, fh = face
    gc_margin_x = int(fw * 3.0)
    gc_margin_top = int(fh * 4.0)
    gc_margin_bot = int(fh * 6.0)
    gc_x1 = max(0, fx - gc_margin_x)
    gc_y1 = max(0, fy - gc_margin_top)
    gc_x2 = min(orig_w, fx + fw + gc_margin_x)
    gc_y2 = min(orig_h, fy + fh + gc_margin_bot)
    gc_rect = (gc_x1, gc_y1, gc_x2 - gc_x1, gc_y2 - gc_y1)

    gc_mask = _np.zeros((orig_h, orig_w), _np.uint8)
    gc_mask[:] = _cv2.GC_PR_FGD
    border = 5
    gc_mask[:border, :] = _cv2.GC_PR_BGD
    gc_mask[-border:, :] = _cv2.GC_PR_BGD
    gc_mask[:, :border] = _cv2.GC_PR_BGD
    gc_mask[:, -border:] = _cv2.GC_PR_BGD

    bgd_model = _np.zeros((1, 65), _np.float64)
    fgd_model = _np.zeros((1, 65), _np.float64)
    try:
        _cv2.grabCut(_np.zeros((orig_h, orig_w, 3), _np.uint8), gc_mask, gc_rect,
                     bgd_model, fgd_model, 5, _cv2.GC_INIT_WITH_RECT)
        gc_fg = _np.where((gc_mask == _cv2.GC_FGD) | (gc_mask == _cv2.GC_PR_FGD), 255, 0).astype(_np.uint8)
        gc_coverage = (gc_fg > 0).sum() / gc_fg.size * 100
        if gc_coverage > (person_binary > 0).sum() / person_binary.size * 100:
            return gc_fg
    except Exception:
        pass
    return person_binary


def _face_ellipse_fallback(orig_h: int, orig_w: int) -> "_np.ndarray":
    """Face-ellipse fallback for person detection."""
    import cv2 as _cv2
    import numpy as _np

    try:
        from app.services.head_detector import _detect_faces
        faces = _detect_faces(_np.zeros((orig_h, orig_w, 3), _np.uint8))
    except Exception:
        faces = []

    if not faces:
        return _np.zeros((orig_h, orig_w), _np.uint8)

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

    body_mask = _np.zeros((orig_h, orig_w), _np.uint8)
    ell_cx = (body_x1 + body_x2) // 2
    ell_cy = (body_y1 + body_y2) // 2
    ell_w = (body_x2 - body_x1) // 2
    ell_h = (body_y2 - body_y1) // 2
    _cv2.ellipse(body_mask, (ell_cx, ell_cy), (ell_w, ell_h), 0, 0, 360, 255, -1)
    return body_mask


async def detect_all_persons(
    se10,
    image_bytes: bytes,
    job_id: str,
    orig_h: int,
    orig_w: int,
    min_area_pct: float = 5.0,
    include_pose: bool = True,
) -> tuple[list, dict, str | None]:
    """Detect ALL persons in the image (multi-person support).

    Unlike detect_person_with_fallbacks which returns only the largest person,
    this returns all detected persons above min_area_pct as PersonData objects.

    Returns:
        (persons, person_seg, pose_cn_b64) — persons is a list of PersonData,
        or ([], {}, None) if no persons detected.
    """
    from .person_data import PersonData, create_persons_from_se10

    # Primary detection
    person_seg = await se10.segment(
        image_bytes=image_bytes, filename=f"{job_id}_person.jpg",
        classes="person, woman, man", box_threshold=0.20, text_threshold=0.15,
        mode="person", detector="ensemble", include_pose=include_pose,
    )
    pose_cn_b64 = person_seg.get("controlnet_image") if include_pose else None

    if not person_seg.get("detected") or not person_seg.get("masks"):
        return [], person_seg, pose_cn_b64

    persons = create_persons_from_se10(person_seg, orig_h, orig_w, min_area_pct)

    if not persons:
        # Retry with lower thresholds
        logger.warning("Job %s: no persons above %.1f%%, retrying with lower thresholds",
                       job_id, min_area_pct)
        person_seg_retry = await se10.segment(
            image_bytes=image_bytes, filename=f"{job_id}_person_retry.jpg",
            classes="person, woman, man", box_threshold=0.10, text_threshold=0.08,
            mode="person", detector="ensemble", include_pose=include_pose,
        )
        if person_seg_retry.get("detected") and person_seg_retry.get("masks"):
            persons = create_persons_from_se10(person_seg_retry, orig_h, orig_w, min_area_pct)
            if persons:
                person_seg = person_seg_retry
                if include_pose and person_seg_retry.get("controlnet_image"):
                    pose_cn_b64 = person_seg_retry["controlnet_image"]

    logger.info("Job %s: detected %d person(s) above %.1f%% threshold",
                job_id, len(persons), min_area_pct)

    return persons, person_seg, pose_cn_b64
