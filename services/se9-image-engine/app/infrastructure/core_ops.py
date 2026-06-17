"""
SE9 Image Engine — Core Operations

Clean-room rewrite of FOOOCUS modules/core.py (341 lines).
Convenience wrappers for operators and ksampler.

Key changes from FOOOCUS:
- Functions instead of global operator instances
- Uses SE9 operators.py instead of ldm_patched.contrib.external
- Lazy torch imports
- Thread-safe
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)


def load_model(ckpt_filename: str, vae_filename: Optional[str] = None):
    """Load a checkpoint file and return a StableDiffusionModel.

    Wraps checkpoint.load_checkpoint_guess_config into a StableDiffusionModel.

    Args:
        ckpt_filename: Path to the checkpoint file (.safetensors, .ckpt, etc.).
        vae_filename: Optional separate VAE file.

    Returns:
        StableDiffusionModel with unet, clip, vae, clip_vision loaded.
    """
    from app.services.checkpoint import load_checkpoint_guess_config
    from app.services.model_base import StableDiffusionModel

    try:
        from modules.config import path_embeddings
    except ImportError:
        path_embeddings = "models/embeddings"

    unet, clip, vae, vae_fn, clip_vision = load_checkpoint_guess_config(
        ckpt_filename,
        embedding_directory=path_embeddings,
        vae_filename_param=vae_filename,
    )

    return StableDiffusionModel(
        unet=unet, clip=clip, vae=vae,
        clip_vision=clip_vision,
        filename=ckpt_filename, vae_filename=vae_fn,
    )


def load_controlnet(ckpt_filename: str):
    """Load a ControlNet model from file.

    Args:
        ckpt_filename: Path to the ControlNet checkpoint.

    Returns:
        ControlNet model instance.
    """
    import ldm_patched.modules.controlnet
    return ldm_patched.modules.controlnet.load_controlnet(ckpt_filename)


def generate_empty_latent(
    width: int = 1024, height: int = 1024, batch_size: int = 1
) -> Dict[str, Any]:
    """Generate an empty latent tensor.

    Args:
        width: Width in pixels (must be divisible by 8).
        height: Height in pixels (must be divisible by 8).
        batch_size: Number of images.

    Returns:
        Dict with 'samples' tensor.
    """
    from app.infrastructure.operators import EmptyLatentImage
    op = EmptyLatentImage()
    return op.generate(width=width, height=height, batch_size=batch_size)[0]


def decode_vae(
    vae, latent_image: Dict[str, Any], tiled: bool = False
) -> Any:
    """Decode latent samples to pixel images.

    Args:
        vae: VAE model instance.
        latent_image: Dict with 'samples' tensor.
        tiled: Whether to use tiled decoding.

    Returns:
        Decoded pixel tensor [B, C, H, W].
    """
    from app.infrastructure.operators import VAEDecode, VAEDecodeTiled

    if tiled:
        op = VAEDecodeTiled()
    else:
        op = VAEDecode()

    return op.decode(samples=latent_image, vae=vae)[0]


def encode_vae(vae, pixels, tiled: bool = False) -> Dict[str, Any]:
    """Encode pixel images to latent samples.

    Args:
        vae: VAE model instance.
        pixels: Pixel tensor [B, C, H, W].
        tiled: Whether to use tiled encoding.

    Returns:
        Dict with 'samples' latent tensor.
    """
    from app.infrastructure.operators import VAEEncode, VAEEncodeTiled

    if tiled:
        op = VAEEncodeTiled()
    else:
        op = VAEEncode()

    return op.encode(pixels=pixels, vae=vae)[0]


def encode_vae_inpaint(vae, pixels, mask) -> Tuple:
    """Encode an image with inpainting mask for VAE.

    Applies mask to pixels before encoding, returns latent + mask.

    Args:
        vae: VAE model instance.
        pixels: Pixel tensor [B, C, H, W] in [0, 1].
        mask: Mask tensor [B, H, W] or [H, W].

    Returns:
        (latent, latent_mask) tuple.
    """
    import torch

    assert mask.ndim == 3 and pixels.ndim == 4
    assert mask.shape[-1] == pixels.shape[-2]
    assert mask.shape[-2] == pixels.shape[-3]

    w = mask.round()[..., None]
    pixels = pixels * (1 - w) + 0.5 * w

    latent = vae.encode(pixels)
    B, C, H, W = latent.shape

    latent_mask = mask[:, None, :, :]
    latent_mask = torch.nn.functional.interpolate(
        latent_mask, size=(H * 8, W * 8), mode="bilinear"
    ).round()
    latent_mask = torch.nn.functional.max_pool2d(latent_mask, (8, 8)).round().to(latent)

    return latent, latent_mask


def apply_freeu(model, b1: float = 1.3, b2: float = 1.4,
                s1: float = 0.9, s2: float = 0.2):
    """Apply FreeU v2 patching to a model.

    Args:
        model: ModelPatcher instance.
        b1: Skip connection scale for first block.
        b2: Skip connection scale for second block.
        s1: Fourier filter scale for first block.
        s2: Fourier filter scale for second block.

    Returns:
        Patched model.
    """
    from app.infrastructure.operators import FreeU_V2
    op = FreeU_V2()
    return op.patch(model=model, b1=b1, b2=b2, s1=s1, s2=s2)[0]


def apply_controlnet(
    positive, negative, control_net, image,
    strength: float = 1.0, start_percent: float = 0.0, end_percent: float = 1.0,
):
    """Apply ControlNet conditioning.

    Args:
        positive: Positive conditioning.
        negative: Negative conditioning.
        control_net: ControlNet model.
        image: Control image tensor.
        strength: Control strength [0, 1].
        start_percent: Start percentage.
        end_percent: End percentage.

    Returns:
        (positive_out, negative_out) tuple.
    """
    from app.infrastructure.operators import ControlNetApplyAdvanced
    op = ControlNetApplyAdvanced()
    return op.apply_controlnet(
        positive=positive, negative=negative,
        control_net=control_net, image=image,
        strength=strength, start_percent=start_percent,
        end_percent=end_percent,
    )


def ksampler(
    model,
    positive,
    negative,
    latent: Dict[str, Any],
    seed: Optional[int] = None,
    steps: int = 30,
    cfg: float = 7.0,
    sampler_name: str = "dpmpp_2m_sde_gpu",
    scheduler: str = "karras",
    denoise: float = 1.0,
    disable_noise: bool = False,
    start_step: Optional[int] = None,
    last_step: Optional[int] = None,
    force_full_denoise: bool = False,
    callback_function: Optional[Callable] = None,
    refiner=None,
    refiner_switch: int = -1,
    previewer_start: Optional[int] = None,
    previewer_end: Optional[int] = None,
    sigmas=None,
    noise_mean=None,
    disable_preview: bool = False,
) -> Dict[str, Any]:
    """Run the sampling process (KSampler).

    This is the core sampling function that drives the diffusion process.

    Args:
        model: ModelPatcher with the UNet to sample from.
        positive: Positive conditioning tensor.
        negative: Negative conditioning tensor.
        latent: Dict with 'samples' tensor.
        seed: Random seed for noise generation.
        steps: Number of sampling steps.
        cfg: Classifier-free guidance scale.
        sampler_name: Name of the sampler (e.g. 'dpmpp_2m_sde_gpu').
        scheduler: Name of the scheduler (e.g. 'karras').
        denoise: Denoising strength [0, 1].
        disable_noise: If True, use zero noise.
        start_step: Starting step index.
        last_step: Last step index.
        force_full_denoise: Force full denoising.
        callback_function: Callback(step, x0, x, total_steps, preview) for progress.
        refiner: Optional refiner ModelPatcher.
        refiner_switch: Step at which to switch to refiner.
        previewer_start: Start step for preview.
        previewer_end: End step for preview.
        sigmas: Optional custom sigma schedule.
        noise_mean: Optional noise mean tensor.
        disable_preview: Disable step preview generation.

    Returns:
        Dict with 'samples' tensor of denoised latent.
    """
    import torch
    from app.services.model_manager import get_model_manager

    manager = get_model_manager()

    if sigmas is not None:
        sigmas = sigmas.clone().to(manager.device)

    latent_image = latent["samples"]

    if disable_noise:
        noise = torch.zeros(
            latent_image.size(),
            dtype=latent_image.dtype,
            layout=latent_image.layout,
            device="cpu",
        )
    else:
        batch_inds = latent.get("batch_index", None)
        noise = ldm_patched.modules.sample.prepare_noise(
            latent_image, seed, batch_inds
        )

    if isinstance(noise_mean, torch.Tensor):
        noise = noise + noise_mean - torch.mean(noise, dim=1, keepdim=True)

    noise_mask = latent.get("noise_mask", None)

    # Previewer
    from app.infrastructure.core_ops import _get_previewer
    previewer = _get_previewer(model)

    if previewer_start is None:
        previewer_start = 0
    if previewer_end is None:
        previewer_end = steps

    def callback(step, x0, x, total_steps):
        from app.services.model_manager import get_model_manager
        get_model_manager().throw_if_interrupted()
        y = None
        if previewer is not None and not disable_preview:
            y = previewer(x0, previewer_start + step, previewer_end)
        if callback_function is not None:
            callback_function(previewer_start + step, x0, x, previewer_end, y)

    try:
        import modules.sample_hijack
        modules.sample_hijack.current_refiner = refiner
        modules.sample_hijack.refiner_switch_step = refiner_switch

        import ldm_patched.modules.samplers
        ldm_patched.modules.samplers.sample = modules.sample_hijack.sample_hacked

        samples = ldm_patched.modules.sample.sample(
            model, noise, steps, cfg, sampler_name, scheduler,
            positive, negative, latent_image,
            denoise=denoise, disable_noise=disable_noise,
            start_step=start_step, last_step=last_step,
            force_full_denoise=force_full_denoise, noise_mask=noise_mask,
            callback=callback, disable_pbar=False, seed=seed, sigmas=sigmas,
        )

        out = latent.copy()
        out["samples"] = samples
    finally:
        import modules.sample_hijack
        modules.sample_hijack.current_refiner = None

    return out


# ---------------------------------------------------------------------------
# VAE Approx Previewer
# ---------------------------------------------------------------------------

_vae_approx_cache: Dict[str, Any] = {}


class VAEApprox:
    """Small convnet for latent preview during sampling."""

    def __init__(self):
        import torch
        super().__init__()
        self.conv1 = torch.nn.Conv2d(4, 8, (7, 7))
        self.conv2 = torch.nn.Conv2d(8, 16, (5, 5))
        self.conv3 = torch.nn.Conv2d(16, 32, (3, 3))
        self.conv4 = torch.nn.Conv2d(32, 64, (3, 3))
        self.conv5 = torch.nn.Conv2d(64, 32, (3, 3))
        self.conv6 = torch.nn.Conv2d(32, 16, (3, 3))
        self.conv7 = torch.nn.Conv2d(16, 8, (3, 3))
        self.conv8 = torch.nn.Conv2d(8, 3, (3, 3))
        self.current_type = None

    def forward(self, x):
        import torch
        extra = 11
        x = torch.nn.functional.interpolate(x, (x.shape[2] * 2, x.shape[3] * 2))
        x = torch.nn.functional.pad(x, (extra, extra, extra, extra))
        for layer in [self.conv1, self.conv2, self.conv3, self.conv4,
                       self.conv5, self.conv6, self.conv7, self.conv8]:
            x = layer(x)
            x = torch.nn.functional.leaky_relu(x, 0.1)
        return x


def _get_previewer(model):
    """Get or create the VAE approx previewer for latent preview."""
    import torch
    import einops

    from app.services.model_manager import get_model_manager
    manager = get_model_manager()

    try:
        from modules.config import path_vae_approx
    except ImportError:
        path_vae_approx = "models/vae_approx"

    try:
        import ldm_patched.modules.latent_formats
        is_sdxl = isinstance(
            model.model.latent_format,
            ldm_patched.modules.latent_formats.SDXL,
        )
    except (ImportError, AttributeError):
        is_sdxl = True

    vae_approx_filename = os.path.join(
        path_vae_approx,
        "xlvaeapp.pth" if is_sdxl else "vaeapp_sd15.pth",
    )

    if vae_approx_filename in _vae_approx_cache:
        vae_approx_model = _vae_approx_cache[vae_approx_filename]
    else:
        if not os.path.exists(vae_approx_filename):
            return None

        sd = torch.load(vae_approx_filename, map_location="cpu", weights_only=True)
        vae_approx_model = VAEApprox()
        vae_approx_model.load_state_dict(sd)
        del sd
        vae_approx_model.eval()

        if manager.should_use_fp16():
            vae_approx_model.half()
            vae_approx_model.current_type = torch.float16
        else:
            vae_approx_model.float()
            vae_approx_model.current_type = torch.float32

        vae_approx_model.to(manager.device)
        _vae_approx_cache[vae_approx_filename] = vae_approx_model

    def preview_function(x0, step, total_steps):
        with torch.no_grad():
            x_sample = x0.to(vae_approx_model.current_type)
            x_sample = vae_approx_model(x_sample) * 127.5 + 127.5
            x_sample = einops.rearrange(x_sample, "b c h w -> b h w c")[0]
            x_sample = x_sample.cpu().numpy().clip(0, 255).astype(np.uint8)
            return x_sample

    return preview_function
