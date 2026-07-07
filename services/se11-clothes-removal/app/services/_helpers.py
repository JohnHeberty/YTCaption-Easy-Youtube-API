"""Shared helper functions for SE11 Clothes Removal pipelines."""
from __future__ import annotations

import base64
from dataclasses import dataclass


# ─── Shared Constants ────────────────────────────────────────────────────────

CLOTHES_CLASSES = (
    "spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, "
    "clothing, garment, skirt, pants, shorts, jeans, sweater, jacket, "
    "coat, hoodie, t-shirt"
)

DEFAULT_CLOTHES_NEGATIVE = (
    "clothes, fabric, bra, straps, underwear, top, blouse, shirt, "
    "dress, skirt, pattern, floral, textile, garment, "
    "text, watermark, deformed, blurry, cartoon, anime, painting, CGI, "
    "extra limbs, disfigured, poorly drawn face, mutated hands, "
    "bad anatomy, deformed skin, wrinkled, scarred"
)


# ─── Scoring Weights ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ScoringWeights:
    """Weights for composite scoring (lower score = better)."""
    skin: float = 0.40
    head: float = 0.20
    landmark: float = 0.30
    clothes: float = 0.10
    early_stop: float = 5.0


SCORING = ScoringWeights()


# ─── Base64 / Image Helpers ──────────────────────────────────────────────────

def decode_image(image_input: str) -> bytes:
    """Decode image from URL, data URI, or raw base64."""
    if image_input.startswith(("http://", "https://")):
        import httpx
        resp = httpx.get(image_input, timeout=30)
        resp.raise_for_status()
        return resp.content
    if "," in image_input and image_input.startswith("data:"):
        image_input = image_input.split(",", 1)[1]
    return base64.b64decode(fix_b64_padding(image_input))


def to_data_uri(b64_str: str, mime: str = "image/png") -> str:
    """Wrap base64 string as data URI."""
    if b64_str.startswith("data:"):
        return b64_str
    return f"data:{mime};base64,{b64_str}"


def strip_data_uri(data_uri: str) -> str:
    """Remove data URI prefix, return raw base64."""
    if "," in data_uri and data_uri.startswith("data:"):
        return data_uri.split(",", 1)[1]
    return data_uri


def fix_b64_padding(s: str) -> str:
    """Fix base64 padding if missing."""
    missing = len(s) % 4
    if missing:
        s += "=" * (4 - missing)
    return s


# ─── Mask Helpers ────────────────────────────────────────────────────────────

def combine_masks(masks: list[str], orig_h: int, orig_w: int):
    """Combine multiple base64 masks into a single binary mask."""
    import cv2 as _cv2
    import numpy as _np
    combined = None
    for mb in masks:
        raw = strip_data_uri(mb)
        c_bytes = base64.b64decode(fix_b64_padding(raw))
        cm = _cv2.imdecode(_np.frombuffer(c_bytes, _np.uint8), _cv2.IMREAD_GRAYSCALE)
        if cm is None:
            continue
        if cm.shape[:2] != (orig_h, orig_w):
            cm = _cv2.resize(cm, (orig_w, orig_h))
        cb = (cm > 127).astype(_np.uint8) * 255
        combined = cb if combined is None else _cv2.bitwise_or(combined, cb)
    return combined


# ─── Skin Detection ──────────────────────────────────────────────────────────

def detect_skin_hsv(img) -> float:
    """Detect skin exposure using HSV color range (local, fast, no SE10).

    Returns skin_pct (0.0-100.0) — percentage of image pixels classified as skin.
    HSV range tuned for diverse skin tones:
      H: 0-30 (warm hues)
      S: 15-170 (moderate saturation — excludes white/grey)
      V: 60-255 (excludes very dark shadows)
    """
    import cv2 as _cv2
    import numpy as _np
    hsv = _cv2.cvtColor(img, _cv2.COLOR_BGR2HSV)
    lower_skin = _np.array([0, 15, 60], dtype=_np.uint8)
    upper_skin = _np.array([30, 170, 255], dtype=_np.uint8)
    skin_mask = _cv2.inRange(hsv, lower_skin, upper_skin)
    kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))
    skin_mask = _cv2.morphologyEx(skin_mask, _cv2.MORPH_OPEN, kernel, iterations=1)
    skin_mask = _cv2.morphologyEx(skin_mask, _cv2.MORPH_CLOSE, kernel, iterations=2)
    return float((skin_mask > 0).sum() / skin_mask.size * 100)


# ─── Composite Scoring ──────────────────────────────────────────────────────

def compute_composite_score(
    skin_ratio: float,
    head_avg: float,
    clothes_pct: float,
    max_landmark: float,
) -> float:
    """Compute composite score from four metrics (lower = better).

    skin_ratio: result_skin_pct / original_skin_pct (>1.0 = more skin = GOOD)
                We use (1 - ratio) so that more skin → lower score → better.
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
