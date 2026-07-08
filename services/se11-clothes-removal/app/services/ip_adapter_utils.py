"""IP-Adapter utility functions for NSFW pipelines.

Extracted from pipeline_nsfw.py and pipeline_nsfw_experimental.py.
"""
from __future__ import annotations

import numpy as _np


def build_clothes_neutral_ref(
    orig_img: _np.ndarray,
    clothes_mask: _np.ndarray,
    person_binary: _np.ndarray,
    head_mask: _np.ndarray | None = None,
) -> _np.ndarray:
    """Create IP-Adapter reference with clothing neutralized (Leffa-style).

    Replaces clothing area with mean skin tone + subtle noise so the
    IP-Adapter encoder cannot extract clothing texture features.
    Keeps face/hair/pose/body-shape intact — only clothing is neutralized.

    This is the direct analog of Leffa's insight (CVPR 2025): control what
    the encoder sees to prevent attention leaking to clothing regions.

    Args:
        orig_img: BGR image (uint8).
        clothes_mask: Binary mask of clothing regions.
        person_binary: Binary mask of person silhouette.
        head_mask: Optional binary mask of head (hair+face).
            If provided, uses skin pixels from arms/neck/face edges
            (more accurate skin tone). If None, uses exposed skin
            (person minus clothes).
    """
    import cv2 as _cv2

    if clothes_mask is None or _cv2.countNonZero(clothes_mask) == 0:
        return orig_img.copy()

    h, w = orig_img.shape[:2]
    ref = orig_img.copy()

    # 1. Determine skin sampling region
    if head_mask is not None:
        # Production mode: use exposed skin from arms, neck, face edges
        skin_mask = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(clothes_mask))
        skin_mask = _cv2.bitwise_and(skin_mask, _cv2.bitwise_not(head_mask))
        if _cv2.countNonZero(skin_mask) < 100:
            skin_mask = head_mask.copy()
    else:
        # Experimental mode: use person minus clothes
        skin_mask = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(clothes_mask))

    # 2. Sample skin pixels in HSV
    hsv = _cv2.cvtColor(orig_img, _cv2.COLOR_BGR2HSV)
    skin_pixels = hsv[skin_mask > 0]
    if len(skin_pixels) > 0:
        mean_h = _np.median(skin_pixels[:, 0])
        mean_s = _np.median(skin_pixels[:, 1])
        mean_v = _np.median(skin_pixels[:, 2])
    else:
        mean_h, mean_s, mean_v = 15, 80, 180

    # 3. Create neutral skin fill: solid tone + subtle noise
    fill_hsv = _np.full((h, w, 3), [mean_h, mean_s, mean_v], dtype=_np.uint8)
    noise = _np.random.normal(0, 8, (h, w, 3)).astype(_np.int16)
    fill_hsv = _np.clip(fill_hsv.astype(_np.int16) + noise, 0, 255).astype(_np.uint8)
    fill_bgr = _cv2.cvtColor(fill_hsv, _cv2.COLOR_HSV2BGR)

    # 4. Blur the fill slightly for organic look
    fill_bgr = _cv2.GaussianBlur(fill_bgr, (5, 5), 2.0)

    # 5. Composite: replace clothing area with neutral fill
    clothes_eroded = clothes_mask.copy()
    ke = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))
    clothes_eroded = _cv2.erode(clothes_eroded, ke, iterations=1)

    mask_f = clothes_eroded.astype(_np.float32) / 255.0
    mask_f = _cv2.GaussianBlur(mask_f, (15, 15), 5.0)

    ref = (ref.astype(_np.float32) * (1 - mask_f[:, :, None]) +
           fill_bgr.astype(_np.float32) * mask_f[:, :, None])
    ref = _np.clip(ref, 0, 255).astype(_np.uint8)

    return ref
