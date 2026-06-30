"""Adaptive head/face detection using OpenCV Haarcascade + person silhouette.

Creates ELIPTICAL masks clipped to the person silhouette — never boxes.
This prevents artificial rectangular edges that confuse the inpainting model.
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


def _detect_faces(orig_img):
    """Detect faces using haarcascade. Returns list of (x, y, w, h)."""
    cascade = _get_face_cascade()
    if cascade is None or orig_img is None:
        return []
    try:
        import cv2
        gray = cv2.cvtColor(orig_img, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(20, 20))
        return list(faces) if len(faces) > 0 else []
    except Exception as exc:
        logger.warning("Haarcascade failed: %s", exc)
        return []


def _ellipse_from_face(fx, fy, fw, fh, h, w, person_binary,
                        expand_w=0.5, expand_up=1.5, expand_down=0.3):
    """Create an elliptical mask centered on the face, clipped to person silhouette.

    Args:
        fx, fy, fw, fh: face bounding box
        h, w: image dimensions
        person_binary: person silhouette mask
        expand_w: horizontal expansion as fraction of fw
        expand_up: upward expansion as fraction of fh (hair region)
        expand_down: downward expansion as fraction of fh (neck region)
    """
    import cv2
    import numpy as np

    face_cx = fx + fw // 2
    face_cy = fy + fh // 2

    # Ellipse dimensions
    e_w = int(fw * (1 + expand_w * 2))
    e_h_top = int(fh * expand_up)
    e_h_bot = int(fh * expand_down)
    e_h = e_h_top + e_h_bot

    # Center shifted upward (hair is above face center)
    e_cy = fy + fh // 2 - e_h_top + e_h // 2

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(mask,
                (face_cx, e_cy),
                (e_w // 2, e_h // 2),
                0, 0, 360, 255, -1)

    # Clip to person silhouette
    mask = cv2.bitwise_and(mask, person_binary)
    return mask


def detect_head_mask(
    orig_img,
    person_binary,
    person_bbox: tuple[int, int, int, int],
    max_head_pct: float = 0.45,
    neck_margin_below: float = 0.50,
    dilate_kernel_size: int = 15,
    dilate_iterations: int = 2,
):
    """Detect head using face detection + elliptical mask clipped to person silhouette.

    1. Detect face with haarcascade
    2. Create elliptical mask centered on face, expanded upward for hair
    3. Clip to person silhouette (no box edges)
    4. Dilate slightly for safety margin
    5. Clip bottom to prevent growing into body

    Falls back to top percentage of person bbox if no face found.
    """
    import cv2
    import numpy as np

    h, w = person_binary.shape[:2]
    px, py, pw, ph = person_bbox
    max_head_h = int(ph * max_head_pct)

    faces = _detect_faces(orig_img)

    head_mask = np.zeros_like(person_binary)

    if len(faces) > 0:
        face = max(faces, key=lambda f: f[2] * f[3])
        fx, fy, fw, fh = face

        # Create elliptical mask around face
        head_mask = _ellipse_from_face(
            fx, fy, fw, fh, h, w, person_binary,
                                        expand_w=0.5, expand_up=1.5, expand_down=neck_margin_below,
        )

        logger.debug("Face (%d,%d,%d,%d) -> elliptical head mask", fx, fy, fw, fh)
    else:
        # Fallback: top max_head_pct of person bbox — still use ellipse
        cx = px + pw // 2
        cy = py + max_head_h // 2
        mask = np.zeros_like(person_binary)
        cv2.ellipse(mask, (cx, cy), (pw // 2, max_head_h // 2), 0, 0, 360, 255, -1)
        head_mask = cv2.bitwise_and(mask, person_binary)
        logger.debug("No face -> fallback elliptical top %d%%", int(max_head_pct * 100))

    # Dilate for safety margin
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_kernel_size, dilate_kernel_size))
    head_mask = cv2.dilate(head_mask, kernel, iterations=dilate_iterations)

    # Find head bottom from original face detection to clip
    if len(faces) > 0:
        face = max(faces, key=lambda f: f[2] * f[3])
        _, fy2, _, fh2 = face
        head_bottom = min(h, fy2 + fh2 + int(fh2 * neck_margin_below))
    else:
        head_bottom = py + max_head_h

    head_mask[head_bottom:, :] = 0  # clip below head_bottom
    head_mask = cv2.bitwise_and(head_mask, person_binary)

    return head_mask


def detect_face_only(
    orig_img,
    person_binary,
    margin_above: float = 0.50,
    margin_below: float = 0.70,
    margin_sides: float = 0.40,
):
    """Detect face region using elliptical mask clipped to person silhouette.

    Returns a smooth elliptical mask of the face area — never a box.
    Used for face protection during inpainting.
    """
    import cv2
    import numpy as np

    h, w = person_binary.shape[:2]
    face_mask = np.zeros_like(person_binary)

    faces = _detect_faces(orig_img)
    if len(faces) == 0:
        return face_mask

    face = max(faces, key=lambda f: f[2] * f[3])
    fx, fy, fw, fh = face

    face_cx = fx + fw // 2
    face_cy = fy + fh // 2

    # Ellipse with margins
    e_w = int(fw * (1 + margin_sides * 2))
    e_h_top = int(fh * margin_above)
    e_h_bot = int(fh * margin_below)
    e_h = e_h_top + e_h_bot
    e_cy = fy + fh // 2 - e_h_top + e_h // 2

    cv2.ellipse(face_mask,
                (face_cx, e_cy),
                (e_w // 2, e_h // 2),
                0, 0, 360, 255, -1)

    # Clip to person silhouette
    face_mask = cv2.bitwise_and(face_mask, person_binary)

    logger.debug("Face-only ellipse: (%d,%d,%d,%d) margin=(%d,%d,%d)",
                 fx, fy, fw, fh, int(fw * margin_sides), int(fh * margin_above), int(fh * margin_below))

    return face_mask
