"""ESRGAN upscaler — lazy-loaded 4x super-resolution."""
from __future__ import annotations

import collections
from common.log_utils import get_logger

import numpy as np
import torch

logger = get_logger(__name__)

_model = None


def _load_model():
    """Lazy-load ESRGAN model on first use."""
    global _model
    if _model is not None:
        return _model

    from ldm_patched.pfn.architecture.RRDB import RRDBNet as ESRGAN
    from ldm_patched.contrib.external_upscale_model import ImageUpscaleWithModel

    model_path = _resolve_upscale_model()
    logger.info("Loading ESRGAN upscaler from %s", model_path)

    sd = torch.load(model_path, map_location="cpu", weights_only=True)
    sdo = collections.OrderedDict()
    for k, v in sd.items():
        sdo[k.replace("residual_block_", "RDB")] = v
    del sd

    net = ESRGAN(sdo)
    net.cpu()
    net.eval()

    _model = {"net": net, "upsampler": ImageUpscaleWithModel()}
    logger.info("ESRGAN upscaler loaded")
    return _model


def _resolve_upscale_model() -> str:
    """Resolve upscale model path from config or common locations."""
    import os
    from app.core.config import get_settings

    settings = get_settings()
    model_dir = getattr(settings, "model_dir", "./data/models")
    upscale_dir = os.path.join(model_dir, "upscale_models")

    # 4x-UltraSharp (highest priority — better color preservation than x4plus)
    candidates = [
        os.path.join(upscale_dir, "4x-UltraSharp.pth"),
        os.path.join(upscale_dir, "RealESRGAN_x4plus.pth"),
        os.path.join(upscale_dir, "RealESRGAN_x4plus_anime_6B.pth"),
        os.path.join(upscale_dir, "fooocus_upscaler_s409985e5.bin"),
    ]

    # Also check modules config paths
    try:
        from modules.config import paths_upscale_models
        if paths_upscale_models:
            for d in paths_upscale_models:
                for name in ["4x-UltraSharp.pth", "RealESRGAN_x4plus.pth",
                             "RealESRGAN_x4plus_anime_6B.pth", "fooocus_upscaler_s409985e5.bin"]:
                    p = os.path.join(d, name)
                    if os.path.exists(p):
                        return p
    except Exception as e:
        logger.debug("modules.config.paths_upscale_models not available: %s", e)

    for p in candidates:
        if os.path.exists(p):
            return p

    raise FileNotFoundError(
        f"Upscale model not found. Searched: {candidates}. "
        "Download 4x-UltraSharp.pth to data/models/upscale_models/"
    )


def numpy_to_pytorch(img: np.ndarray) -> torch.Tensor:
    """Convert numpy HWC image to pytorch tensor (batch dim only, no permute).

    Matches modules/core.py numpy_to_pytorch: adds batch dim, keeps HWC.
    ImageUpscaleWithModel handles HWC->CHW conversion internally.
    """
    x = img.astype(np.float32) / 255.0
    x = x[None]
    x = np.ascontiguousarray(x.copy())
    x = torch.from_numpy(x).float()
    return x


def pytorch_to_numpy(x: torch.Tensor) -> list:
    """Convert pytorch tensor list to numpy images.

    Matches modules/core.py pytorch_to_numpy: clips, converts, returns list.
    """
    return [np.clip(255. * y.cpu().numpy(), 0, 255).astype(np.uint8) for y in x]


def perform_upscale(img: np.ndarray) -> np.ndarray:
    """Perform 4x ESRGAN upscale on a numpy image.

    Args:
        img: Input image as numpy array (HWC, uint8)

    Returns:
        Upscaled image as numpy array (HWC, uint8)
    """
    model = _load_model()

    x = numpy_to_pytorch(img)
    result = model["upsampler"].upscale(model["net"], x)

    # upscale() returns a list of tensors [N, C, H, W] or a single tensor
    if isinstance(result, (list, tuple)):
        tensor = result[0]
    else:
        tensor = result

    # Convert to numpy: handle both [C,H,W] and [H,W,C] shapes
    arr = tensor.cpu().numpy()
    if arr.ndim == 4:  # [N, C, H, W]
        arr = arr[0]
    if arr.ndim == 3 and arr.shape[0] in (1, 3, 4):  # [C, H, W] -> [H, W, C]
        arr = np.transpose(arr, (1, 2, 0))
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)

    return arr
