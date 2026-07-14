"""Debug visualization utilities for NSFW pipelines.

Extracted from pipeline_nsfw.py and pipeline_nsfw_experimental.py.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as _np

from common.log_utils import get_logger

logger = get_logger(__name__)


def save_debug_image(
    output_dir: str,
    num: int,
    name: str,
    img: "_np.ndarray",
) -> None:
    """Save a debug image with numbered prefix."""
    import cv2 as _cv2
    try:
        path = os.path.join(output_dir, f"{num:02d}_{name}.png")
        _cv2.imwrite(path, img)
    except Exception as exc:
        logger.warning("Debug save %s failed: %s", name, exc)


def build_debug_grid(
    panels: list,
    cell_w: int = 400,
    cell_h: int = 600,
    cols: int = 3,
    font_scale: float = 0.55,
    padding: int = 4,
) -> "_np.ndarray":
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


def save_mask_overlay(
    output_dir: str,
    num: int,
    name: str,
    orig_img: "_np.ndarray",
    inpaint_mask: "_np.ndarray",
    clothes_mask: "_np.ndarray | None" = None,
    hair_mask: "_np.ndarray | None" = None,
) -> None:
    """Save mask overlay on original image for visual debugging."""
    import cv2 as _cv2
    try:
        inpaint_pct = (inpaint_mask > 0).sum() / inpaint_mask.size * 100
        mask_overlay = orig_img.copy()
        mask_color = _cv2.cvtColor(inpaint_mask, _cv2.COLOR_GRAY2BGR)
        mask_color[:, :, 0] = 0
        mask_color[:, :, 2] = 0
        mask_overlay = _cv2.addWeighted(mask_overlay, 0.6, mask_color, 0.4, 0)
        _cv2.putText(mask_overlay,
                     f"Inpaint mask: {inpaint_pct:.1f}%",
                     (10, 25), _cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        save_debug_image(output_dir, num, name, mask_overlay)
    except Exception as e:
        logger.debug("Failed to save inpaint mask overlay: %s", e)


def save_detection_metadata(
    output_dir: str,
    person_seg: dict,
    clothes_seg: dict,
    person_binary: "_np.ndarray",
    clothes_pct: float,
    orig_w: int,
    orig_h: int,
    faceid_embedding: list | None = None,
    base_model: str = "",
    filename: str = "detection_meta.json",
) -> None:
    """Save SE10 detection metadata as JSON."""
    import json
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
        }
        if faceid_embedding is not None:
            seg_meta["faceid"] = True
        if base_model:
            seg_meta["base_model"] = base_model
        with open(os.path.join(output_dir, filename), "w") as f:
            json.dump(seg_meta, f, indent=2)
    except Exception as e:
        logger.debug("Failed to save detection metadata: %s", e)


def save_garment_masks(
    output_dir: str,
    clothes_seg: dict,
    orig_h: int,
    orig_w: int,
) -> None:
    """Save individual garment masks from SE10 detection."""
    import base64
    import cv2 as _cv2
    import numpy as _np

    from .image_utils import strip_data_uri as _strip_data_uri, fix_b64_padding as _fix_b64_padding

    if not clothes_seg.get("detected") or not clothes_seg.get("masks"):
        return

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
                save_debug_image(output_dir, 20 + gi, f"garment_{gi}_{gclass}", gm_color)
        except Exception as e:
            logger.debug("Failed to save garment mask %d: %s", gi, e)
