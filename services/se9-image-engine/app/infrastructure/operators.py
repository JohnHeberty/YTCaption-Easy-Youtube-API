"""
SE9 Image Engine — Operators

Clean-room rewrite of FOOOCUS ldm_patched/contrib/external.py (key operators)
and external_freelunch.py (FreeU_V2).

Operators wrap ldm_patched primitives into clean callable objects.
These are used by pipeline.py and core_ops.py for the generation pipeline.

Key changes from FOOOCUS:
- No ComfyUI node registration (INPUT_TYPES, RETURN_TYPES, etc.)
- Clean class-based operators with __call__ interface
- Lazy torch imports
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class EmptyLatentImage:
    """Generate an empty latent tensor.

    Wraps ldm_patched.contrib.external.EmptyLatentImage.
    """

    def generate(self, width: int = 1024, height: int = 1024, batch_size: int = 1):
        """Generate an empty latent tensor.

        Args:
            width: Width in pixels (must be divisible by 8).
            height: Height in pixels (must be divisible by 8).
            batch_size: Number of images in batch.

        Returns:
            Dict with 'samples' tensor of shape [batch, 4, height//8, width//8].
        """
        import torch
        from ldm_patched.modules.model_management import unet_dtype

        latent = torch.zeros(
            [batch_size, 4, height // 8, width // 8],
            dtype=unet_dtype(),
            device="cpu",
        )
        return ({"samples": latent},)


class VAEDecode:
    """Decode latent samples to pixel images.

    Wraps ldm_patched.contrib.external.VAEDecode.
    """

    def decode(self, samples: Dict[str, Any], vae=None, tile_size: int = 512, tiled: bool = False):
        """Decode latent tensor to pixels.

        Args:
            samples: Dict with 'samples' tensor.
            vae: VAE model instance.
            tile_size: Tile size for tiled decoding.
            tiled: Whether to use tiled decoding.

        Returns:
            Decoded pixel tensor [B, C, H, W].
        """
        import torch

        latent = samples["samples"]

        if tiled:
            return self._decode_tiled(vae, latent, tile_size)
        else:
            return self._decode_standard(vae, latent)

    def _decode_standard(self, vae, latent):
        """Standard VAE decode."""
        try:
            return vae.decode(latent)
        except Exception as e:
            logger.warning(f"VAE decode failed: {e}, trying with fp32")
            with torch.autocast("cuda", enabled=False):
                return vae.decode(latent.float())

    def _decode_tiled(self, vae, latent, tile_size: int = 512):
        """Tiled VAE decode for large images."""
        import torch

        # Simple tiled decode: split latent into tiles, decode each, reassemble
        B, C, H, W = latent.shape
        if H <= tile_size // 8 and W <= tile_size // 8:
            return self._decode_standard(vae, latent)

        # Use vae's built-in tiled decode if available
        if hasattr(vae, 'decode_tiled'):
            return vae.decode_tiled(latent, tile_size=tile_size)

        # Fallback: decode full
        logger.info("Tiled decode not available, using standard decode")
        return self._decode_standard(vae, latent)


class VAEEncode:
    """Encode pixel images to latent samples.

    Wraps ldm_patched.contrib.external.VAEEncode.
    """

    def encode(self, pixels, vae=None, tile_size: int = 512, tiled: bool = False):
        """Encode pixel tensor to latent.

        Args:
            pixels: Pixel tensor [B, C, H, W] in [0, 1] or [0, 255].
            vae: VAE model instance.
            tile_size: Tile size for tiled encoding.
            tiled: Whether to use tiled encoding.

        Returns:
            Dict with 'samples' latent tensor.
        """
        import torch

        if tiled and hasattr(vae, 'encode_tiled'):
            latent = vae.encode_tiled(pixels, tile_size=tile_size)
        else:
            latent = vae.encode(pixels)

        return {"samples": latent}


class VAEDecodeTiled:
    """Decode with tiled mode for large images."""

    def decode(self, samples, vae=None, tile_size: int = 512):
        return VAEDecode().decode(samples, vae=vae, tile_size=tile_size, tiled=True)


class VAEEncodeTiled:
    """Encode with tiled mode for large images."""

    def encode(self, pixels, vae=None, tile_size: int = 512):
        return VAEEncode().encode(pixels, vae=vae, tile_size=tile_size, tiled=True)


class FreeU_V2:
    """Apply FreeU v2 patching to a model.

    Clean-room rewrite of ldm_patched/contrib/external_freelunch.py:FreeU_V2.

    FreeU enhances diffusion quality by rescaling skip connections
    and applying Fourier filtering to the skip features.
    """

    def patch(self, model, b1: float = 1.3, b2: float = 1.4,
              s1: float = 0.9, s2: float = 0.2):
        """Apply FreeU v2 patching to a model.

        Args:
            model: ModelPatcher instance.
            b1: Skip connection scale for first block.
            b2: Skip connection scale for second block.
            s1: Fourier filter scale for first block.
            s2: Fourier filter scale for second block.

        Returns:
            Tuple of (patched_model,).
        """
        import torch

        model_channels = model.model.model_config.unet_config["model_channels"]
        scale_dict = {
            model_channels * 4: (b1, s1),
            model_channels * 2: (b2, s2),
        }
        on_cpu_devices = {}

        def fourier_filter(x, threshold, scale):
            """Apply Fourier filter to tensor."""
            x_freq = torch.fft.fftn(x.float(), dim=(-2, -1))
            x_freq = torch.fft.fftshift(x_freq, dim=(-2, -1))

            B, C, H, W = x_freq.shape
            mask = torch.ones((B, C, H, W), device=x.device)
            crow, ccol = H // 2, W // 2
            mask[..., crow - threshold:crow + threshold,
                       ccol - threshold:ccol + threshold] = scale
            x_freq = x_freq * mask

            x_freq = torch.fft.ifftshift(x_freq, dim=(-2, -1))
            x_filtered = torch.fft.ifftn(x_freq, dim=(-2, -1)).real
            return x_filtered.to(x.dtype)

        def output_block_patch(h, hsp, transformer_options):
            """Patch output blocks with FreeU scaling."""
            scale = scale_dict.get(h.shape[1], None)
            if scale is not None:
                h = h.clone()
                h[:, :h.shape[1] // 2] = h[:, :h.shape[1] // 2] * scale[0]

                if hsp.device not in on_cpu_devices:
                    try:
                        hsp = fourier_filter(hsp, threshold=1, scale=scale[1])
                    except Exception:
                        logger.debug(f"Device {hsp.device} doesn't support torch.fft, using CPU")
                        on_cpu_devices[hsp.device] = True
                        hsp = fourier_filter(hsp.cpu(), threshold=1, scale=scale[1]).to(hsp.device)
                else:
                    hsp = fourier_filter(hsp.cpu(), threshold=1, scale=scale[1]).to(hsp.device)

            return h, hsp

        m = model.clone()
        m.set_model_output_block_patch(output_block_patch)
        return (m,)


class ControlNetApplyAdvanced:
    """Apply ControlNet conditioning.

    Wraps ldm_patched.contrib.external.ControlNetApplyAdvanced.
    Stub for Sprint 4 — full implementation in Sprint 7.
    """

    def apply_controlnet(
        self, positive, negative, control_net, image,
        strength: float = 1.0, start_percent: float = 0.0, end_percent: float = 1.0
    ):
        """Apply ControlNet to conditioning.

        Args:
            positive: Positive conditioning.
            negative: Negative conditioning.
            control_net: ControlNet model.
            image: Control image tensor.
            strength: Control strength [0, 1].
            start_percent: Start percentage for control.
            end_percent: End percentage for control.

        Returns:
            (positive_out, negative_out) tuple.
        """
        # Stub — full implementation in Sprint 7
        logger.warning("ControlNetApplyAdvanced is a stub — full implementation pending")
        return positive, negative


class ModelSamplingDiscrete:
    """Model sampling discrete wrapper.

    Stub for Sprint 4 — full implementation in Sprint 8 (performance modes).
    """

    def patch(self, model, sampling: str = "eps"):
        logger.debug(f"ModelSamplingDiscrete.patch(sampling={sampling}) — stub")
        return (model,)


class ModelSamplingContinuousEDM:
    """Model sampling continuous EDM wrapper.

    Stub for Sprint 4 — full implementation in Sprint 8 (performance modes).
    """

    def patch(self, model, sampling: str = "eps", sigma_max: float = 1.0):
        logger.debug(f"ModelSamplingContinuousEDM.patch(sampling={sampling}) — stub")
        return (model,)
