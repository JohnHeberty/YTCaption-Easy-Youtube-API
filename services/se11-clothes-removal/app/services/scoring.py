"""Composite scoring and skin detection."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as _np

from .config_loader import get_nsfw_config, SCORING


def detect_skin_hsv(img) -> float:
    """Detect skin exposure using HSV color range (local, fast, no SE10).

    Returns skin_pct (0.0-100.0) — percentage of image pixels classified as skin.
    """
    import cv2 as _cv2
    import numpy as _np

    _skin_cfg = get_nsfw_config("production")
    hsv = _cv2.cvtColor(img, _cv2.COLOR_BGR2HSV)
    lower_skin = _np.array(_skin_cfg.sd_hsv_lower, dtype=_np.uint8)
    upper_skin = _np.array(_skin_cfg.sd_hsv_upper, dtype=_np.uint8)
    skin_mask = _cv2.inRange(hsv, lower_skin, upper_skin)
    kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (_skin_cfg.sd_morph_kernel_size, _skin_cfg.sd_morph_kernel_size))
    skin_mask = _cv2.morphologyEx(skin_mask, _cv2.MORPH_OPEN, kernel, iterations=_skin_cfg.sd_open_iterations)
    skin_mask = _cv2.morphologyEx(skin_mask, _cv2.MORPH_CLOSE, kernel, iterations=_skin_cfg.sd_close_iterations)
    return float((skin_mask > 0).sum() / skin_mask.size * 100)


def compute_composite_score(
    skin_ratio: float,
    head_avg: float,
    clothes_pct: float,
    max_landmark: float,
) -> float:
    """Compute composite score from four metrics (lower = better).

    skin_ratio: result_skin_pct / original_skin_pct (>1.0 = more skin = GOOD)
    head_avg:   face landmark drift (lower = better)
    clothes_pct: residual clothing (lower = better)
    max_landmark: worst landmark drift (lower = better)
    """
    skin_score = 1.0 - skin_ratio
    head_clamped = min(head_avg, 100.0)
    clothes_clamped = min(clothes_pct, 100.0)
    landmark_clamped = min(max_landmark, 100.0)
    score = (
        SCORING.skin * skin_score +
        SCORING.head * head_clamped +
        SCORING.landmark * landmark_clamped +
        SCORING.clothes * clothes_clamped
    )
    return round(score, 3)
