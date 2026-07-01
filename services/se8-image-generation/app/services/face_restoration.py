"""Face restoration — GFPGAN/CodeFormer via facexlib and ldm_patched."""
from __future__ import annotations

from typing import Any
from common.log_utils import get_logger

import cv2
import numpy as np
import torch

logger = get_logger(__name__)

_face_restoration_model = None
_face_restore_helper = None


def _get_face_restore_helper() -> Any:
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
        logger.warning("facexlib not available, face restoration disabled")
        return None
    except Exception as e:
        logger.warning("Failed to initialize FaceRestoreHelper: %s", e)
        return None


def _load_restoration_model(model_name: str = "CodeFormer") -> Any:
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
            checkpoint = torch.load(model_path, map_location="cpu")
            state_dict = checkpoint
            if isinstance(checkpoint, dict):
                if "params_ema" in checkpoint:
                    state_dict = checkpoint["params_ema"]
                elif "params-ema" in checkpoint:
                    state_dict = checkpoint["params-ema"]
                elif "params" in checkpoint:
                    state_dict = checkpoint["params"]
            model = CodeFormer(state_dict)
        elif model_name == "GFPGAN":
            from ldm_patched.pfn.architecture.face.gfpganv1_clean_arch import GFPGANv1Clean
            model_path = _resolve_model_path("gfpgan")
            checkpoint = torch.load(model_path, map_location="cpu")
            state_dict = checkpoint
            if isinstance(checkpoint, dict):
                if "params_ema" in checkpoint:
                    state_dict = checkpoint["params_ema"]
                elif "params-ema" in checkpoint:
                    state_dict = checkpoint["params-ema"]
                elif "params" in checkpoint:
                    state_dict = checkpoint["params"]
                elif "state_dict" in checkpoint:
                    state_dict = checkpoint["state_dict"]
            model = GFPGANv1Clean(state_dict)
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
) -> tuple[np.ndarray, int]:
    """Restore faces in an image using GFPGAN or CodeFormer.

    Args:
        img: Input image (HWC, RGB, uint8)
        model_name: 'CodeFormer' or 'GFPGAN'
        fidelity: CodeFormer fidelity slider (0.0-1.0), only used for CodeFormer

    Returns:
        Tuple of (image with restored faces (HWC, RGB, uint8), number of faces restored)
    """
    model = _load_restoration_model(model_name)
    if model is None:
        logger.warning("Face restoration model not available, returning original")
        return img, 0

    helper = _get_face_restore_helper()
    if helper is None:
        logger.warning("Face restore helper not available, returning original")
        return img, 0

    try:
        # Detect faces
        helper.clean_all()
        helper.read_image(img)
        helper.get_face_landmarks_5(only_center_face=False)

        faces_count = len(helper.all_landmarks_5)
        if faces_count == 0:
            logger.info("No faces detected, skipping restoration")
            return img, 0

        # Align and warp each face
        helper.align_warp_face()
        helper.get_inverse_affine()

        # Restore each face
        for i, cropped_face in enumerate(helper.cropped_faces):
            # Facexlib may return batched faces (N,H,W,C); normalize to (H,W,C)
            if cropped_face.ndim == 4 and cropped_face.shape[0] == 1:
                cropped_face = cropped_face[0]
            elif cropped_face.ndim == 4 and cropped_face.shape[-1] == 1:
                cropped_face = cropped_face.squeeze(-1)

            # Convert to tensor (C, H, W) with batch dim
            face_tensor = torch.from_numpy(cropped_face).permute(2, 0, 1).unsqueeze(0).float() / 255.0
            face_tensor = face_tensor.to(next(model.parameters()).device)

            with torch.no_grad():
                if model_name == "CodeFormer":
                    # CodeFormer with controllable feature transformation
                    restored = model(face_tensor, w=fidelity)
                else:
                    restored = model(face_tensor)

            # Models return (tensor, aux_info) tuple; image is the first element
            if isinstance(restored, tuple):
                restored = restored[0]

            # Model output may be (1, C, H, W) or (C, H, W); normalize to (H, W, C)
            if restored.ndim == 4 and restored.shape[0] == 1:
                restored = restored[0]
            restored = restored.permute(1, 2, 0).clamp(0, 1).float().cpu().numpy()
            restored = (restored * 255).astype(np.uint8)

            helper.add_restored_face(restored)

        # Paste restored faces back
        result = helper.paste_faces_to_input_image()
        if result is None:
            return img, faces_count

        return result, faces_count

    except Exception as e:
        logger.warning("Face restoration failed: %s", e)
        return img, 0
