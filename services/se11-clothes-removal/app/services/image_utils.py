"""Base64, image decode/encode, and mask utilities."""
from __future__ import annotations

import base64
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as _np


def fix_b64_padding(s: str) -> str:
    """Fix base64 padding if missing."""
    missing = len(s) % 4
    if missing:
        s += "=" * (4 - missing)
    return s


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
