"""Face detection and alignment for IP-Adapter face tasks.

Clean-room rewrite of FOOOCUS Fooocus/extras/face_crop.py (50 lines).
Uses facexlib for face detection and alignment.
"""
import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_face_restore_helper = None


def _get_face_restore_helper():
    """Lazy-load FaceRestoreHelper singleton."""
    global _face_restore_helper
    if _face_restore_helper is not None:
        return _face_restore_helper

    try:
        from extras.facexlib.utils.face_restoration_helper import FaceRestoreHelper
        _face_restore_helper = FaceRestoreHelper(
            face_detection_model="retinaface_resnet50",
            upscale_factor=1,
            face_size=512,
            crop_ratio=1,
            det_model="retinaface_resnet50",
            save_ext="png",
            device="cpu",
        )
        return _face_restore_helper
    except ImportError:
        logger.warning("facexlib not available, face detection disabled")
        return None


def align_warp_face(
    img_rgb: np.ndarray,
    landmark: np.ndarray,
    border_mode: int = cv2.BORDER_REFLECT_101,
) -> Optional[np.ndarray]:
    """Estimate affine transform from 5-point landmark to template, warp face.

    Args:
        img_rgb: Input image (HWC, RGB, uint8)
        landmark: 5-point face landmarks (5, 2)
        border_mode: OpenCV border mode for warp

    Returns:
        Aligned face image or None if transform fails
    """
    # Template face landmarks (5 points: left eye, right eye, nose, left mouth, right mouth)
    template = np.array([
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ], dtype=np.float32)

    # Estimate affine transform
    M = cv2.estimateAffinePartial2D(landmark, template, method=cv2.LMEDS)[0]
    if M is None:
        logger.warning("Failed to estimate affine transform from landmarks")
        return None

    # Warp face
    output_size = (112, 112)
    aligned = cv2.warpAffine(
        img_rgb, M, output_size, borderMode=border_mode, borderValue=0
    )
    return aligned


def crop_image(img_rgb: np.ndarray) -> np.ndarray:
    """Detect faces and return the largest aligned face.

    Args:
        img_rgb: Input image (HWC, RGB, uint8)

    Returns:
        Aligned face image (112x112, RGB, uint8)
    """
    helper = _get_face_restore_helper()
    if helper is None:
        # Fallback: return center crop
        h, w = img_rgb.shape[:2]
        size = min(h, w)
        y = (h - size) // 2
        x = (w - size) // 2
        return cv2.resize(img_rgb[y:y + size, x:x + size], (112, 112))

    try:
        # Detect faces
        helper.clean_all()
        helper.read_image(img_rgb)
        helper.get_face_landmarks_5(only_center_face=True)
        if len(helper.all_landmarks_5) == 0:
            logger.warning("No face detected, returning center crop")
            h, w = img_rgb.shape[:2]
            size = min(h, w)
            y = (h - size) // 2
            x = (w - size) // 2
            return cv2.resize(img_rgb[y:y + size, x:x + size], (112, 112))

        landmark = helper.all_landmarks_5[0]
        aligned = align_warp_face(img_rgb, landmark)
        if aligned is None:
            # Fallback
            h, w = img_rgb.shape[:2]
            size = min(h, w)
            y = (h - size) // 2
            x = (w - size) // 2
            return cv2.resize(img_rgb[y:y + size, x:x + size], (112, 112))

        return aligned
    except Exception as e:
        logger.warning("Face detection failed: %s, returning center crop", e)
        h, w = img_rgb.shape[:2]
        size = min(h, w)
        y = (h - size) // 2
        x = (w - size) // 2
        return cv2.resize(img_rgb[y:y + size, x:x + size], (112, 112))
