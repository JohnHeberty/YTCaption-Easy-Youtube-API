"""Image preprocessors for ControlNet — Canny pyramid + CPDS.

Clean-room rewrite of FOOOCUS Fooocus/extras/preprocessors.py (81 lines).
"""
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def centered_canny(
    x: np.ndarray,
    canny_low_threshold: int = 100,
    canny_high_threshold: int = 200,
) -> np.ndarray:
    """Single-channel Canny edge detection. Returns float32 0-1."""
    return cv2.Canny(x, canny_low_threshold, canny_high_threshold).astype(np.float32) / 255.0


def centered_canny_color(
    x: np.ndarray,
    canny_low_threshold: int = 100,
    canny_high_threshold: int = 200,
) -> np.ndarray:
    """Per-channel Canny on 3-channel image. Stacks results."""
    results = []
    for i in range(x.shape[2]):
        results.append(centered_canny(x[:, :, i], canny_low_threshold, canny_high_threshold))
    return np.stack(results, axis=-1)


def pyramid_canny_color(
    x: np.ndarray,
    canny_low_threshold: int = 100,
    canny_high_threshold: int = 200,
) -> np.ndarray:
    """Multi-scale Canny: runs at 9 scales (0.2 to 1.0), accumulates with weighted blending."""
    h, w = x.shape[:2]
    acc = None
    scales = np.linspace(0.2, 1.0, 9)

    for scale in scales:
        new_h = max(int(h * scale), 16)
        new_w = max(int(w * scale), 16)
        resized = cv2.resize(x, (new_w, new_h), interpolation=cv2.INTER_AREA)
        edge = centered_canny_color(resized, canny_low_threshold, canny_high_threshold)

        if acc is None:
            acc = edge
        else:
            # Upscale accumulator to match current edge size
            acc = cv2.resize(acc, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            # Blend: 75% accumulator + 25% new edge
            acc = acc * 0.75 + edge * 0.25

    return acc


def norm255(x: np.ndarray, low: float = 4.0, high: float = 96.0) -> np.ndarray:
    """Percentile-based normalization: clips to [low, high] percentile range, rescales to 0-255."""
    x_min = np.percentile(x, low)
    x_max = np.percentile(x, high)
    if x_max - x_min < 1e-6:
        return np.zeros_like(x, dtype=np.uint8)
    x = np.clip(x, x_min, x_max)
    x = ((x - x_min) / (x_max - x_min) * 255).astype(np.uint8)
    return x


def canny_pyramid(
    x: np.ndarray,
    canny_low_threshold: int = 100,
    canny_high_threshold: int = 200,
) -> np.ndarray:
    """Full Canny pipeline: pyramid_canny_color -> sum channels -> norm255 -> uint8."""
    edges = pyramid_canny_color(x, canny_low_threshold, canny_high_threshold)
    # Sum across channels
    edge_sum = edges.sum(axis=-1)
    # Normalize to 0-255
    result = norm255(edge_sum)
    return result.astype(np.uint8)


def cpds(x: np.ndarray) -> np.ndarray:
    """Color-to-Pencil-Drawings-Sketch: Gaussian blur + decolor + offset computation."""
    # Gaussian blur
    blurred = cv2.GaussianBlur(x, (0, 0), sigmaX=0.8)

    # cv2.decolor (research algorithm for color-to-gray)
    gray, color_boost = cv2.decolor(blurred)

    # Compute structure offset (Euclidean distance between original and boosted grayscale)
    gray_3ch = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR).astype(np.float32)
    offset = np.sqrt(np.sum((x.astype(np.float32) - color_boost.astype(np.float32)) ** 2, axis=-1))

    # Normalize and combine
    result = norm255(offset)
    return result.astype(np.uint8)
