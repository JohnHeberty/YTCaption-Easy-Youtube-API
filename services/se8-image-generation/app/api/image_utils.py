"""Image I/O utilities for SE8 Image Engine.

Pure functions for encoding/decoding images between numpy arrays, base64, and files.
No business logic — only data transformation.
"""

from __future__ import annotations

import base64
import urllib.request
from io import BytesIO

import numpy as np
from PIL import Image


def ndarray_to_base64png(narray: np.ndarray | None) -> str:
    """Encode a numpy array (HWC, uint8) as a base64 PNG string."""
    if narray is None:
        return ""
    img = Image.fromarray(narray)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def read_input_image(input_image: str | bytes | None) -> np.ndarray | None:
    """Load an image from URL, base64 data URI, file path, or raw bytes.

    Returns an RGB numpy array (HWC, uint8) or None if input is invalid.
    """
    if input_image is None:
        return None

    if isinstance(input_image, str):
        if input_image in ("", "None", "null", "string", "none"):
            return None
        if input_image.startswith("http"):
            req = urllib.request.Request(
                input_image, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req) as resp:
                img_bytes = resp.read()
            return _bytes_to_ndarray(img_bytes)
        if input_image.startswith("data:"):
            img_data = base64.b64decode(input_image.split(",", 1)[1])
            return _bytes_to_ndarray(img_data)
        img = Image.open(input_image)
        return _pil_to_ndarray(img)

    if isinstance(input_image, bytes):
        return _bytes_to_ndarray(input_image)

    return None


def _bytes_to_ndarray(img_bytes: bytes) -> np.ndarray:
    """Decode raw image bytes to RGB numpy array."""
    return _pil_to_ndarray(Image.open(BytesIO(img_bytes)))


def _pil_to_ndarray(img: Image.Image) -> np.ndarray:
    """Convert PIL Image to RGB numpy array (HWC, uint8)."""
    return np.flip(np.array(img), axis=-1).copy()
