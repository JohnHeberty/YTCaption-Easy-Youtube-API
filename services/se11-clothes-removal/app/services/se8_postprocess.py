"""SE8 upscale and face restore helpers."""
from __future__ import annotations

import base64
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as _np

from .image_utils import to_data_uri, fix_b64_padding


async def upscale_result(se8, img, logger_ref=None) -> "_np.ndarray | None":
    """Upscale image via SE8 4x-UltraSharp. Returns upscaled image or None."""
    import cv2 as _cv2
    import numpy as _np

    try:
        _, buf = _cv2.imencode(".png", img)
        b64 = to_data_uri(base64.b64encode(buf).decode("utf-8"), mime="image/png")
        result = await se8.upscale(image_b64=b64, scale=2.0)
        if result and result.get("base64"):
            upscaled_b64 = result["base64"]
            if "," in upscaled_b64 and upscaled_b64.startswith("data:"):
                upscaled_b64 = upscaled_b64.split(",", 1)[1]
            upscaled_b64 = fix_b64_padding(upscaled_b64)
            upscaled_bytes = base64.b64decode(upscaled_b64)
            upscaled_img = _cv2.imdecode(_np.frombuffer(upscaled_bytes, _np.uint8), _cv2.IMREAD_COLOR)
            if upscaled_img is not None:
                return upscaled_img
    except Exception as exc:
        if logger_ref:
            logger_ref.warning("Upscale failed: %s", exc)
    return None


async def restore_face(se8, img, model: str = "CodeFormer", fidelity: float = 0.5,
                       logger_ref=None) -> "_np.ndarray | None":
    """Restore face via SE8. Returns restored image or None."""
    import cv2 as _cv2
    import numpy as _np

    try:
        _, buf = _cv2.imencode(".png", img)
        b64 = to_data_uri(base64.b64encode(buf).decode("utf-8"), mime="image/png")
        result = await se8.restore_face(image_b64=b64, model=model, fidelity=fidelity)
        if result and result.get("base64"):
            restored_b64 = result["base64"]
            if "," in restored_b64 and restored_b64.startswith("data:"):
                restored_b64 = restored_b64.split(",", 1)[1]
            restored_bytes = base64.b64decode(restored_b64)
            restored_img = _cv2.imdecode(_np.frombuffer(restored_bytes, _np.uint8), _cv2.IMREAD_COLOR)
            if restored_img is not None:
                return restored_img
    except Exception as exc:
        if logger_ref:
            logger_ref.warning("Face restore failed: %s", exc)
    return None
