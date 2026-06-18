"""ESRGAN upscaler — lazy-loaded 4x super-resolution."""
import collections
import logging
from typing import Optional

import numpy as np
import torch

logger = logging.getLogger(__name__)

_model = None


def _load_model():
    """Lazy-load ESRGAN model on first use."""
    global _model
    if _model is not None:
        return _model

    from ldm_patched.pfn.architecture.RRDB import RRDBNet
    from ldm_patched.contrib.external_upscale_model import ImageUpscaleWithModel

    from app.services.model_manager import get_model_manager

    model_path = _resolve_upscale_model()
    logger.info("Loading ESRGAN upscaler from %s", model_path)

    state_dict = torch.load(model_path, map_location="cpu")
    # Rename keys: residual_block_ -> RDB (ESRGAN convention)
    new_state_dict = collections.OrderedDict()
    for k, v in state_dict.items():
        new_key = k.replace("residual_block_", "RDB.")
        new_state_dict[new_key] = v

    net = RRDBNet(
        num_in_ch=3,
        num_out_ch=3,
        num_feat=64,
        num_block=23,
        num_grow_ch=32,
        scale=4,
    )
    net.load_state_dict(new_state_dict, strict=False)
    net.eval()

    mm = get_model_manager()
    device = mm.device
    net = net.to(device)

    _model = ImageUpscaleWithModel(net)
    logger.info("ESRGAN upscaler loaded on %s", device)
    return _model


def _resolve_upscale_model() -> str:
    """Resolve upscale model path from config or common locations."""
    import os
    from app.core.config import get_settings

    settings = get_settings()
    model_dir = getattr(settings, "model_dir", "./data/models")
    upscale_dir = os.path.join(model_dir, "upscale_models")

    # Check config paths first
    candidates = [
        os.path.join(upscale_dir, "RealESRGAN_x4plus.pth"),
        os.path.join(upscale_dir, "RealESRGAN_x4plus_anime_6B.pth"),
        os.path.join(upscale_dir, "fooocus_upscaler_s409985e5.bin"),
    ]

    # Also check modules config paths
    try:
        from modules.config import paths_upscale_models
        if paths_upscale_models:
            for d in paths_upscale_models:
                for name in ["RealESRGAN_x4plus.pth", "RealESRGAN_x4plus_anime_6B.pth", "fooocus_upscaler_s409985e5.bin"]:
                    p = os.path.join(d, name)
                    if os.path.exists(p):
                        return p
    except Exception:
        pass

    for p in candidates:
        if os.path.exists(p):
            return p

    raise FileNotFoundError(
        f"Upscale model not found. Searched: {candidates}. "
        "Download RealESRGAN_x4plus.pth or fooocus_upscaler_s409985e5.bin to data/models/upscale_models/"
    )


def numpy_to_pytorch(img: np.ndarray) -> torch.Tensor:
    """Convert numpy HWC image to pytorch NCHW tensor."""
    x = torch.from_numpy(img.astype(np.float32) / 255.0)
    if len(x.shape) == 2:
        x = x.unsqueeze(-1)
    x = x.permute(2, 0, 1).unsqueeze(0)
    return x


def pytorch_to_numpy(x: torch.Tensor) -> np.ndarray:
    """Convert pytorch NCHW tensor to numpy HWC image."""
    x = x[0].permute(1, 2, 0).clamp(0, 1).float().cpu().numpy()
    x = (x * 255).astype(np.uint8)
    return x


def perform_upscale(img: np.ndarray) -> np.ndarray:
    """Perform 4x ESRGAN upscale on a numpy image.

    Args:
        img: Input image as numpy array (HWC, uint8)

    Returns:
        Upscaled image as numpy array (HWC, uint8)
    """
    model = _load_model()

    x = numpy_to_pytorch(img)
    x = model.upscale(x)
    result = pytorch_to_numpy(x)

    return result
