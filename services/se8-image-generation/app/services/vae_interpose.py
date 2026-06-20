"""VAE Interpose — latent space translation for SDXL→SD1 refiner swap."""
from __future__ import annotations

import os
from common.log_utils import get_logger

import torch
import torch.nn as nn

logger = get_logger(__name__)

vae_approx_model = None
vae_approx_filename = None


class ResBlock(nn.Module):
    """Residual block with BatchNorm + 3 Conv2d layers + SiLU + Dropout."""

    def __init__(self, ch: int) -> None:
        super().__init__()
        self.norm = nn.BatchNorm2d(ch)
        self.long = nn.Sequential(
            nn.Conv2d(ch, ch, 3, padding=1),
            nn.SiLU(),
            nn.Dropout(0.1),
            nn.Conv2d(ch, ch, 3, padding=1),
            nn.SiLU(),
            nn.Dropout(0.1),
            nn.Conv2d(ch, ch, 3, padding=1),
        )
        self.join = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.join(self.long(x) + x)


class ExtractBlock(nn.Module):
    """Channel expansion block."""

    def __init__(self, ch_in: int, ch_out: int) -> None:
        super().__init__()
        self.short = nn.Conv2d(ch_in, ch_out, 1)
        self.long = nn.Sequential(
            nn.Conv2d(ch_in, ch_out, 3, padding=1),
            nn.SiLU(),
            nn.Dropout(0.1),
            nn.Conv2d(ch_out, ch_out, 3, padding=1),
            nn.SiLU(),
            nn.Dropout(0.1),
            nn.Conv2d(ch_out, ch_out, 3, padding=1),
        )
        self.join = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.join(self.long(x) + self.short(x))


class InterposerModel(nn.Module):
    """Lightweight neural network for latent space translation (SDXL→SD1.5)."""

    def __init__(
        self,
        ch_in: int = 4,
        ch_out: int = 4,
        ch_mid: int = 64,
        scale: float = 1.0,
        blocks: int = 12,
    ) -> None:
        super().__init__()
        self.head = ExtractBlock(ch_in, ch_mid)
        core = [ResBlock(ch_mid) for _ in range(blocks)]
        self.core = nn.Sequential(
            nn.Upsample(scale_factor=1, mode="nearest"),
            *core,
            nn.BatchNorm2d(ch_mid),
            nn.SiLU(),
        )
        self.tail = nn.Conv2d(ch_mid, ch_out, 3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.tail(self.core(self.head(x)))


def _resolve_model_path() -> str:
    """Resolve vae interpose model path."""
    global vae_approx_filename

    if vae_approx_filename is not None and os.path.exists(vae_approx_filename):
        return vae_approx_filename

    from app.core.config import get_settings
    settings = get_settings()
    model_dir = getattr(settings, "model_dir", "./data/models")

    candidates = [
        os.path.join(model_dir, "vae_approx", "xl-to-v1_interposer-v4.0.safetensors"),
        os.path.join(model_dir, "vae_approx", "xl-to-v1_interposer-v3.1.safetensors"),
        os.path.join(model_dir, "xl-to-v1_interposer-v4.0.safetensors"),
    ]

    # Also check modules config paths
    try:
        from modules.config import path_vae_approx
        for name in ["xl-to-v1_interposer-v4.0.safetensors", "xl-to-v1_interposer-v3.1.safetensors"]:
            p = os.path.join(path_vae_approx, name)
            if os.path.exists(p):
                return p
    except Exception:
        pass

    for p in candidates:
        if os.path.exists(p):
            vae_approx_filename = p
            return p

    raise FileNotFoundError(
        f"VAE interpose model not found. Searched: {candidates}. "
        "Download xl-to-v1_interposer-v4.0.safetensors or v3.1"
    )


def parse(x: torch.Tensor) -> torch.Tensor:
    """Translate latent from SDXL space to SD1.5 space.

    Args:
        x: SDXL latent tensor (B, 4, H, W)

    Returns:
        SD1.5-compatible latent tensor (B, 4, H, W)
    """
    global vae_approx_model

    if vae_approx_model is None:
        from safetensors.torch import load_file
        from ldm_patched.modules.model_patcher import ModelPatcher
        from app.services.model_manager import get_model_manager

        model_path = _resolve_model_path()
        logger.info("Loading VAE interpose from %s", model_path)

        mm = get_model_manager()
        device = mm.device

        state_dict = load_file(model_path)
        model = InterposerModel()
        model.load_state_dict(state_dict, strict=False)
        model.eval()

        vae_approx_model = ModelPatcher(
            model,
            load_device=device,
            offload_device="cpu",
        )
        logger.info("VAE interpose loaded on %s", device)

    # Run inference
    x_origin = x
    device = vae_approx_model.load_device

    # Load to GPU if needed
    from ldm_patched.modules.model_management import load_models_gpu
    load_models_gpu([vae_approx_model], vae_approx_model.model_bytes())

    result = vae_approx_model.model(x.to(device)).to(x_origin)
    return result
