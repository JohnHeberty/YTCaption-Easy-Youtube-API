"""Shared helper functions for SE11 Clothes Removal pipelines."""
from __future__ import annotations

import base64


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
