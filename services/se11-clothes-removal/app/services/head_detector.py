"""Adaptive head detection using OpenCV Haarcascade + person silhouette.

Uses face detection to locate the face, then scans the person silhouette
upward to find the full hair extent. Caps head region to a maximum
percentage of person height to avoid protecting too much body.

Fallback: fixed percentage of person bbox (no face found).
"""
from __future__ import annotations

from common.log_utils import get_logger

logger = get_logger(__name__)

_FACE_CASCADE = None


def _get_face_cascade():
    global _FACE_CASCADE
    if _FACE_CASCADE is None:
        import cv2
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _FACE_CASCADE = cv2.CascadeClassifier(cascade_path)
        if _FACE_CASCADE.empty():
            logger.error("Failed to load haarcascade: %s", cascade_path)
            _FACE_CASCADE = None
    return _FACE_CASCADE


def detect_head_mask(
    orig_img,
    person_binary,
    person_bbox: tuple[int, int, int, int],
    max_head_pct: float = 0.40,
    neck_margin_below: float = 0.15,
    dilate_kernel_size: int = 15,
    dilate_iterations: int = 2,
):
    """Detect head using face detection + silhouette scan, capped at max_head_pct.

    1. Detect face with haarcascade
    2. Scan person silhouette upward from face to find hair top
    3. Cap head region to max_head_pct of person height
    4. Dilate sideways/upward only — clip bottom so it doesn't grow into body
    5. Clip to person silhouette

    Falls back to max_head_pct of person bbox if no face found.
    """
    import cv2
    import numpy as np

    px, py, pw, ph = person_bbox
    max_head_h = int(ph * max_head_pct)

    cascade = _get_face_cascade()
    faces = []

    if cascade is not None and orig_img is not None:
        try:
            gray = cv2.cvtColor(orig_img, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(20, 20))
        except Exception as exc:
            logger.warning("Haarcascade failed: %s", exc)

    head_mask = np.zeros_like(person_binary)

    if len(faces) > 0:
        face = max(faces, key=lambda f: f[2] * f[3])
        fx, fy, fw, fh = face

        # Scan upward from face center to find silhouette top (= hair)
        face_cx = fx + fw // 2
        scan_half_w = max(fw // 2, 10)
        person_top_y = fy
        for sy in range(fy, py, -1):
            col = person_binary[sy, max(0, face_cx - scan_half_w):min(person_binary.shape[1], face_cx + scan_half_w)]
            if np.any(col > 127):
                person_top_y = sy
                break

        # Head bottom = face bottom + small neck margin (chin area only)
        head_bottom = min(person_binary.shape[0], fy + fh + int(fh * neck_margin_below))
        # Head top = max silhouette top OR bottom - max_head_h
        head_top = max(person_top_y, head_bottom - max_head_h)
        head_top = max(0, head_top)

        # Slight horizontal expansion
        h_left = max(0, fx - fw // 6)
        h_right = min(person_binary.shape[1], fx + fw + fw // 6)

        head_mask[head_top:head_bottom, h_left:h_right] = 255
        head_mask = cv2.bitwise_and(head_mask, person_binary)

        logger.debug("Face (%d,%d,%d,%d) -> head y=%d-%d (sil_top=%d, max_h=%d)",
                      fx, fy, fw, fh, head_top, head_bottom, person_top_y, max_head_h)

    else:
        # Fallback: top max_head_pct of person bbox
        head_mask[py:py + max_head_h, px:px + pw] = 255
        head_mask = cv2.bitwise_and(head_mask, person_binary)
        head_bottom = py + max_head_h
        logger.debug("No face -> fallback top %d%%", int(max_head_pct * 100))

    # Dilate for safety margin — but clip bottom so it doesn't grow into body
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_kernel_size, dilate_kernel_size))
    head_mask = cv2.dilate(head_mask, kernel, iterations=dilate_iterations)
    head_mask[head_bottom:, :] = 0  # clip below head_bottom
    head_mask = cv2.bitwise_and(head_mask, person_binary)

    return head_mask
