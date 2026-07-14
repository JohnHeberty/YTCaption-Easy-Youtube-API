from __future__ import annotations

"""Shared FaceRestoreHelper singleton for face detection/restoration."""

from typing import Any

from common.log_utils import get_logger

logger = get_logger(__name__)

_face_restore_helper: Any = None


def get_face_restore_helper() -> Any:
    """Lazy-load FaceRestoreHelper singleton."""
    global _face_restore_helper
    if _face_restore_helper is not None:
        return _face_restore_helper

    try:
        from extras.facexlib.utils.face_restoration_helper import FaceRestoreHelper
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        _face_restore_helper = FaceRestoreHelper(
            upscale_factor=1,
            face_size=512,
            crop_ratio=(1, 1),
            det_model="retinaface_resnet50",
            save_ext="png",
            device=device,
        )
        logger.info("FaceRestoreHelper loaded on %s", device)
        return _face_restore_helper
    except ImportError:
        logger.warning("facexlib not available, face detection/restoration disabled")
        return None
    except Exception as e:
        logger.warning("Failed to initialize FaceRestoreHelper: %s", e)
        return None
