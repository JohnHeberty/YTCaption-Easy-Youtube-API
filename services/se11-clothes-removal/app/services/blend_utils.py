"""Blending utilities for face-body compositing.

Provides Laplacian pyramid blending and other multi-scale blending techniques
to reduce collage artifacts when pasting the original face onto a generated body.
"""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def _ensure_float(img: np.ndarray) -> np.ndarray:
    """Convert image to float32 in [0, 1]."""
    if img.dtype == np.uint8:
        return img.astype(np.float32) / 255.0
    if img.max() > 1.0:
        return img.astype(np.float32) / 255.0
    return img.astype(np.float32)


def _build_gaussian_pyramid(img: np.ndarray, levels: int) -> list[np.ndarray]:
    """Build a Gaussian pyramid.

    Args:
        img: Input image (float32, [0, 1]).
        levels: Number of pyramid levels.

    Returns:
        List of pyramid images from largest to smallest.
    """
    pyramid = [img.copy()]
    for _ in range(levels - 1):
        next_level = cv2.pyrDown(pyramid[-1])
        pyramid.append(next_level)
    return pyramid


def _build_laplacian_pyramid(img: np.ndarray, levels: int) -> list[np.ndarray]:
    """Build a Laplacian pyramid from an image.

    Args:
        img: Input image (float32, [0, 1]).
        levels: Number of pyramid levels.

    Returns:
        List of Laplacian pyramid levels.
    """
    gaussian = _build_gaussian_pyramid(img, levels)
    laplacian: list[np.ndarray] = [gaussian[-1]]
    for i in range(levels - 1, 0, -1):
        size = (gaussian[i - 1].shape[1], gaussian[i - 1].shape[0])
        upsampled = cv2.pyrUp(gaussian[i], dstsize=size)
        laplacian_level = gaussian[i - 1] - upsampled
        laplacian.append(laplacian_level)
    laplacian.reverse()
    return laplacian


def _reconstruct_from_laplacian(laplacian: list[np.ndarray]) -> np.ndarray:
    """Reconstruct an image from its Laplacian pyramid."""
    result = laplacian[-1]
    for i in range(len(laplacian) - 2, -1, -1):
        size = (laplacian[i].shape[1], laplacian[i].shape[0])
        result = cv2.pyrUp(result, dstsize=size)
        result = result + laplacian[i]
    return result


def laplacian_blend(
    img_a: np.ndarray,
    img_b: np.ndarray,
    mask: np.ndarray,
    levels: int = 6,
) -> np.ndarray:
    """Blend two images using Laplacian pyramids.

    Low frequencies (color/illumination) are blended smoothly according to the
    mask, while high frequencies (texture/detail) are preserved from each image.
    This reduces visible seams at face-body boundaries.

    Args:
        img_a: First image (uint8 or float, BGR or RGB).
        img_b: Second image (uint8 or float, BGR or RGB).
        mask: Blending weight for img_a per pixel, range [0, 1].
              Values near 1 keep img_a; values near 0 keep img_b.
        levels: Number of Laplacian pyramid levels. Use fewer levels for
                narrower transition bands.

    Returns:
        Blended image as uint8 with same shape as inputs.
    """
    if img_a.shape[:2] != img_b.shape[:2]:
        raise ValueError("img_a and img_b must have the same height and width")
    if img_a.shape[:2] != mask.shape[:2]:
        raise ValueError("mask must match image height and width")

    img_a_f = _ensure_float(img_a)
    img_b_f = _ensure_float(img_b)

    # Normalize mask to [0, 1] float
    if mask.dtype == np.uint8:
        mask_f = mask.astype(np.float32) / 255.0
    else:
        mask_f = mask.astype(np.float32)
        if mask_f.max() > 1.0:
            mask_f = mask_f / 255.0
    mask_f = np.clip(mask_f, 0.0, 1.0)

    # If single-channel mask but images are multi-channel, broadcast
    if mask_f.ndim == 2 and img_a_f.ndim == 3:
        mask_f = mask_f[:, :, np.newaxis]

    # Clamp levels to avoid too-small pyramids
    min_dim = min(img_a.shape[:2])
    max_levels = int(np.floor(np.log2(min_dim))) - 1
    levels = min(levels, max_levels)
    levels = max(3, levels)

    lap_a = _build_laplacian_pyramid(img_a_f, levels)
    lap_b = _build_laplacian_pyramid(img_b_f, levels)

    # Gaussian pyramid of the mask (blends low frequencies smoothly)
    if mask_f.ndim == 3:
        mask_for_pyramid = mask_f[:, :, 0]
    else:
        mask_for_pyramid = mask_f
    mask_pyr = _build_gaussian_pyramid(mask_for_pyramid, levels)

    blended_lap: list[np.ndarray] = []
    for la, lb, gm in zip(lap_a, lap_b, mask_pyr):
        gm = gm[:, :, np.newaxis] if gm.ndim == 2 and la.ndim == 3 else gm
        blended = gm * la + (1.0 - gm) * lb
        blended_lap.append(blended)

    result = _reconstruct_from_laplacian(blended_lap)
    result = np.clip(result * 255.0, 0, 255).astype(np.uint8)
    return result


def blend_face_region(
    original: np.ndarray,
    generated: np.ndarray,
    face_mask: np.ndarray,
    transition_width: int = 35,
    levels: int = 6,
) -> tuple[np.ndarray, np.ndarray]:
    """Blend the original face region into the generated image.

    Builds a smooth transition mask from the face mask using distance transform,
    then applies Laplacian pyramid blending on a tight ROI around the face.

    Args:
        original: Original image containing the face (uint8, BGR).
        generated: Generated image where the face will be pasted (uint8, BGR).
        face_mask: Binary mask of the face region to protect (uint8, 0/255).
        transition_width: Width of the soft transition band in pixels.
        levels: Number of Laplacian pyramid levels.

    Returns:
        Tuple of (blended_image, blend_weight_mask as uint8 0-255).
    """
    h, w = original.shape[:2]
    if face_mask is None or cv2.countNonZero(face_mask) == 0:
        return generated.copy(), np.zeros((h, w), dtype=np.uint8)

    # Distance transform: 1.0 at center, fading to 0.0 at transition_width
    dist = cv2.distanceTransform(face_mask, cv2.DIST_L2, 5).astype(np.float32)
    face_weight = np.clip(dist / max(1, transition_width), 0.0, 1.0)

    # Directional feather: keep hard edges on top/sides, soft only on chin/neck.
    # Find vertical midpoint of the face mask.
    _, fy, _, fh = cv2.boundingRect(face_mask)
    face_cy = fy + fh // 2
    y_coords = np.arange(h)[:, None]
    face_weight = np.where(
        (face_mask > 0) & (y_coords >= face_cy),
        face_weight,
        (face_mask > 0).astype(np.float32),
    )

    # Tight ROI to save computation
    x, y, bw, bh = cv2.boundingRect(face_mask)
    margin = transition_width * 2
    x0, y0 = max(0, x - margin), max(0, y - margin)
    x1, y1 = min(w, x + bw + margin), min(h, y + bh + margin)

    orig_roi = original[y0:y1, x0:x1]
    gen_roi = generated[y0:y1, x0:x1]
    weight_roi = face_weight[y0:y1, x0:x1]

    blended_roi = laplacian_blend(orig_roi, gen_roi, weight_roi, levels=levels)

    result = generated.copy()
    result[y0:y1, x0:x1] = blended_roi

    weight_uint8 = (face_weight * 255).astype(np.uint8)
    return result, weight_uint8
