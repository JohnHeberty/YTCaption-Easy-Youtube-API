"""Face restoration — GFPGAN/CodeFormer via facexlib and ldm_patched.

Clean-room implementation based on FOOOCUS extras/face_crop.py and
ldm_patched/pfn/architecture/face/ model definitions.
"""
import logging
from typing import Optional

import cv2
import numpy as np
import torch

logger = logging.getLogger(__name__)

_face_restoration_model = None
_face_restore_helper = None


def _get_face_restore_helper():
    """Lazy-load FaceRestoreHelper singleton."""
    global _face_restore_helper
    if _face_restore_helper is not None:
        return _face_restore_helper

    try:
        from extras.facexlib.utils.face_restoration_helper import FaceRestoreHelper
        _face_restore_helper = FaceRestoreHelper(
            face_detection_model="retinaface_resnet50",
            upscale_factor=1,
            face_size=512,
            crop_ratio=1,
            det_model="retinaface_resnet50",
            save_ext="png",
            device="cpu",
        )
        return _face_restore_helper
    except ImportError:
        logger.warning("facexlib not available, face restoration disabled")
        return None


def _load_restoration_model(model_name: str = "CodeFormer"):
    """Lazy-load face restoration model.

    Args:
        model_name: 'CodeFormer' or 'GFPGAN'
    """
    global _face_restoration_model
    if _face_restoration_model is not None:
        return _face_restoration_model

    from app.services.model_manager import get_model_manager
    mm = get_model_manager()
    device = mm.device

    try:
        if model_name == "CodeFormer":
            from ldm_patched.pfn.architecture.face.codeformer import CodeFormer
            model_path = _resolve_model_path("codeformer")
            state_dict = torch.load(model_path, map_location="cpu")
            model = CodeFormer()
            model.load_state_dict(state_dict, strict=False)
        elif model_name == "GFPGAN":
            from ldm_patched.pfn.architecture.face.gfpganv1_clean_arch import GFPGANv1Clean
            model_path = _resolve_model_path("gfpgan")
            state_dict = torch.load(model_path, map_location="cpu")
            model = GFPGANv1Clean(
                out_size=512,
                channel_multiplier=2,
                num_mlp=8,
                lr_multiplier=1.0,
            )
            model.load_state_dict(state_dict, strict=False)
        else:
            raise ValueError(f"Unknown face restoration model: {model_name}")

        model.eval()
        model = model.to(device)
        _face_restoration_model = model
        logger.info("Face restoration model %s loaded on %s", model_name, device)
        return model

    except Exception as e:
        logger.warning("Failed to load face restoration model %s: %s", model_name, e)
        return None


def _resolve_model_path(model_type: str) -> str:
    """Resolve face restoration model path."""
    import os
    from app.core.config import get_settings

    settings = get_settings()
    model_dir = getattr(settings, "model_dir", "./data/models")

    candidates = {
        "codeformer": [
            os.path.join(model_dir, "face_restore", "codeformer.pth"),
            os.path.join(model_dir, "codeformer.pth"),
        ],
        "gfpgan": [
            os.path.join(model_dir, "face_restore", "GFPGANv1.4.pth"),
            os.path.join(model_dir, "GFPGANv1.4.pth"),
        ],
    }

    for path in candidates.get(model_type, []):
        if os.path.exists(path):
            return path

    raise FileNotFoundError(
        f"Face restoration model not found. Searched: {candidates.get(model_type, [])}"
    )


def restore_face(
    img: np.ndarray,
    model_name: str = "CodeFormer",
    fidelity: float = 0.5,
) -> np.ndarray:
    """Restore faces in an image using GFPGAN or CodeFormer.

    Args:
        img: Input image (HWC, RGB, uint8)
        model_name: 'CodeFormer' or 'GFPGAN'
        fidelity: CodeFormer fidelity slider (0.0-1.0), only used for CodeFormer

    Returns:
        Image with restored faces (HWC, RGB, uint8)
    """
    model = _load_restoration_model(model_name)
    if model is None:
        logger.warning("Face restoration model not available, returning original")
        return img

    helper = _get_face_restore_helper()
    if helper is None:
        logger.warning("Face restore helper not available, returning original")
        return img

    try:
        # Detect faces
        helper.clean_all()
        helper.read_image(img)
        helper.get_face_landmarks_5(only_center_face=False)

        if len(helper.all_landmarks_5) == 0:
            logger.info("No faces detected, skipping restoration")
            return img

        # Align and warp each face
        helper.align_warp_face()

        # Restore each face
        for i, cropped_face in enumerate(helper.cropped_faces):
            # Convert to tensor
            face_tensor = torch.from_numpy(cropped_face).permute(2, 0, 1).unsqueeze(0).float() / 255.0
            face_tensor = face_tensor.to(next(model.parameters()).device)

            with torch.no_grad():
                if model_name == "CodeFormer":
                    # CodeFormer with controllable feature transformation
                    restored = model(face_tensor, w=fidelity)
                else:
                    restored = model(face_tensor)

            # Convert back to numpy
            restored = restored[0].permute(1, 2, 0).clamp(0, 1).float().cpu().numpy()
            restored = (restored * 255).astype(np.uint8)

            helper.add_restored_face(restored)

        # Paste restored faces back
        helper.paste_faces_to_input_image(upscale_factor=1)

        # Get result
        result = helper.output
        if result is None:
            return img

        return result

    except Exception as e:
        logger.warning("Face restoration failed: %s", e)
        return img
