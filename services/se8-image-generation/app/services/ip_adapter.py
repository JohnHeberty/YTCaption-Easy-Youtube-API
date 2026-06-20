"""IP-Adapter — CLIP vision encoding + cross-attention injection."""
from __future__ import annotations

from typing import Any

from common.log_utils import get_logger

import numpy as np
import torch
import torch.nn as nn

logger = get_logger(__name__)

# Channel dimensions for attention layers
SD_V12_CHANNELS = [320, 320, 640, 640, 1280, 1280, 1280]
SD_XL_CHANNELS = [640, 640, 1280, 1280, 2048, 2048, 2048]

# Global state
clip_vision = None
ip_negative = None
ip_adapters: dict[str, dict[str, Any]] = {}


class ImageProjModel(nn.Module):
    """Linear projection from CLIP embeddings to cross-attention tokens."""

    def __init__(
        self,
        cross_attention_dim: int = 1024,
        clip_embeddings_dim: int = 1024,
        clip_extra_context_tokens: int = 4,
    ) -> None:
        super().__init__()
        self.cross_attention_dim = cross_attention_dim
        self.clip_extra_context_tokens = clip_extra_context_tokens
        self.proj = nn.Linear(clip_embeddings_dim, cross_attention_dim)
        self.norm = nn.LayerNorm(cross_attention_dim)

    def forward(self, image_embeds: torch.Tensor) -> torch.Tensor:
        # image_embeds: (batch, clip_embeddings_dim)
        embeds = self.proj(image_embeds)
        embeds = self.norm(embeds)
        # Reshape to (batch, tokens, dim)
        embeds = embeds.unsqueeze(1).expand(-1, self.clip_extra_context_tokens, -1)
        return embeds


class To_KV(nn.Module):
    """Projects IP-Adapter features to per-layer K/V weights for all UNet attention blocks."""

    def __init__(self, cross_attention_dim: int) -> None:
        super().__init__()
        # Determine channel dimensions based on cross_attention_dim
        if cross_attention_dim == 1280:
            channels = SD_XL_CHANNELS
        else:
            channels = SD_V12_CHANNELS

        self.to_k = nn.ModuleList([nn.Linear(cross_attention_dim, ch) for ch in channels])
        self.to_v = nn.ModuleList([nn.Linear(cross_attention_dim, ch) for ch in channels])

    def load_state_dict_ordered(self, sd: dict) -> None:
        """Load pre-ordered k/v weight pairs from state dict."""
        k_keys = sorted([k for k in sd.keys() if "to_k" in k])
        v_keys = sorted([k for k in sd.keys() if "to_v" in k])

        for i, (k_key, v_key) in enumerate(zip(k_keys, v_keys)):
            if i < len(self.to_k):
                self.to_k[i].weight.data = sd[k_key]
                self.to_v[i].weight.data = sd[v_key]


class IPAdapterModel(nn.Module):
    """Combines image projection model with To_KV layers."""

    def __init__(
        self,
        state_dict: dict,
        plus: bool = False,
        cross_attention_dim: int = 768,
        clip_embeddings_dim: int = 1024,
        clip_extra_context_tokens: int = 4,
        sdxl_plus: bool = False,
    ) -> None:
        super().__init__()

        if plus:
            # Use Resampler for IP-Adapter-Plus
            try:
                from extras.resampler import Resampler
                self.image_proj_model = Resampler(
                    dim=cross_attention_dim,
                    depth=4,
                    dim_head=64,
                    heads=12,
                    num_queries=clip_extra_context_tokens,
                    embedding_dim=clip_embeddings_dim,
                    output_dim=cross_attention_dim,
                    ff_mult=4,
                )
            except ImportError:
                logger.warning("Resampler not available, using basic projection")
                self.image_proj_model = ImageProjModel(
                    cross_attention_dim, clip_embeddings_dim, clip_extra_context_tokens
                )
        else:
            self.image_proj_model = ImageProjModel(
                cross_attention_dim, clip_embeddings_dim, clip_extra_context_tokens
            )

        self.ip_layers = To_KV(cross_attention_dim)

        # Load state dicts
        proj_keys = [k for k in state_dict.keys() if "image_proj" in k or "proj" in k]
        if proj_keys:
            proj_sd = {k.replace("image_proj.", "").replace("proj.", ""): state_dict[k] for k in proj_keys}
            try:
                self.image_proj_model.load_state_dict(proj_sd, strict=False)
            except Exception as e:
                logger.warning("Failed to load image proj weights: %s", e)

        ip_keys = [k for k in state_dict.keys() if "ip_layers" in k]
        if ip_keys:
            ip_sd = {k.replace("ip_layers.", ""): state_dict[k] for k in ip_keys}
            self.ip_layers.load_state_dict_ordered(ip_sd)


def sdp(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, extra_options: dict) -> torch.Tensor:
    """Scaled dot-product attention wrapper."""
    from ldm_patched.modules.attention import optimized_attention
    return optimized_attention(q, k, v, extra_options)


def load_ip_adapter(
    clip_vision_path: str,
    ip_negative_path: str,
    ip_adapter_path: str,
) -> None:
    """Load IP-Adapter: CLIP vision model, negative tensor, and adapter model."""
    global clip_vision, ip_negative

    from ldm_patched.modules.clip_vision import load as load_clip_vision
    from safetensors.torch import load_file

    # Load CLIP vision
    if clip_vision is None:
        logger.info("Loading CLIP vision from %s", clip_vision_path)
        clip_vision = load_clip_vision(clip_vision_path)

    # Load negative embedding
    if ip_negative is None:
        logger.info("Loading IP negative from %s", ip_negative_path)
        ip_negative = load_file(ip_negative_path)

    # Load adapter model
    if ip_adapter_path not in ip_adapters:
        logger.info("Loading IP adapter from %s", ip_adapter_path)
        state_dict = load_file(ip_adapter_path)

        # Detect plus variant
        plus = any("image_proj_model" in k and "resampler" in k.lower() for k in state_dict.keys())
        sdxl_plus = any("to_k_ip.0.weight" in k for k in state_dict.keys())
        cross_attention_dim = 2048 if sdxl_plus else 1280

        model = IPAdapterModel(
            state_dict,
            plus=plus,
            cross_attention_dim=cross_attention_dim,
            clip_embeddings_dim=1024,
            clip_extra_context_tokens=4 if not plus else 16,
            sdxl_plus=sdxl_plus,
        )

        ip_adapters[ip_adapter_path] = {
            "ip_adapter": model,
            "plus": plus,
            "sdxl_plus": sdxl_plus,
        }
        logger.info("IP adapter loaded: plus=%s, sdxl=%s", plus, sdxl_plus)


def clip_preprocess(image: np.ndarray) -> torch.Tensor:
    """Normalize 224x224 image with CLIP mean/std."""
    mean = np.array([0.48145466, 0.4578275, 0.40821073])
    std = np.array([0.26862954, 0.26130258, 0.27577711])

    image = image.astype(np.float32) / 255.0
    image = (image - mean) / std
    image = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0).float()
    return image


def preprocess(img: np.ndarray, ip_adapter_path: str) -> list:
    """Full IP preprocessing: CLIP vision encode -> image projection -> K/V pairs.

    Returns:
        List of [image_embeds, ip_negative_embeds, ip_kvs, ip_unconds]
    """
    global clip_vision, ip_negative

    if clip_vision is None:
        raise RuntimeError("CLIP vision not loaded. Call load_ip_adapter() first.")

    adapter_info = ip_adapters.get(ip_adapter_path)
    if adapter_info is None:
        raise RuntimeError(f"IP adapter not loaded: {ip_adapter_path}")

    ip_adapter = adapter_info["ip_adapter"]

    # Preprocess image for CLIP
    processed = clip_preprocess(img)

    # Encode with CLIP vision
    from app.services.model_manager import get_model_manager
    mm = get_model_manager()
    device = mm.device

    with torch.no_grad():
        clip_output = clip_vision(processed.to(device))
        image_embeds = clip_output["image_embeds"]

        # Project to cross-attention tokens
        ip_tokens = ip_adapter.image_proj_model(image_embeds)

        # Get negative embedding
        if isinstance(ip_negative, dict):
            negative_embeds = ip_negative.get("ip_negative", torch.zeros_like(image_embeds))
        else:
            negative_embeds = torch.zeros_like(image_embeds)

        # Compute K/V for each attention layer
        ip_kvs = []
        for i in range(len(ip_adapter.ip_layers.to_k)):
            k = ip_adapter.ip_layers.to_k[i](ip_tokens)
            v = ip_adapter.ip_layers.to_v[i](ip_tokens)
            ip_kvs.append((k, v))

        ip_unconds = []
        for i in range(len(ip_adapter.ip_layers.to_k)):
            k = ip_adapter.ip_layers.to_k[i](negative_embeds)
            v = ip_adapter.ip_layers.to_v[i](negative_embeds)
            ip_unconds.append((k, v))

    return [image_embeds, negative_embeds, ip_kvs, ip_unconds]


def patch_model(model, tasks: list) -> torch.Tensor:
    """Patch UNet attention blocks to inject IP-adapter K/V.

    Args:
        model: ModelPatcher instance
        tasks: List of [image_embeds, ip_negative, ip_kvs, ip_unconds] per task

    Returns:
        Patched model
    """
    if not tasks:
        return model

    # Clone model for independent patching
    patched_model = model.clone()

    # Track which attention blocks to patch
    # Input blocks: IDs [4, 5] (2 indices) + IDs [7, 8] (10 indices)
    # Output blocks: IDs [0-5] with varying indices
    # Middle block: 10 indices

    for task_idx, task_data in enumerate(tasks):
        if len(task_data) < 4:
            continue
        image_embeds, negative_embeds, ip_kvs, ip_unconds = task_data

        # Register attention patches at specific blocks
        _set_ip_adapter_patches(patched_model, ip_kvs, ip_unconds, task_idx)

    return patched_model


def _set_ip_adapter_patches(model, ip_kvs, ip_unconds, task_idx: int) -> None:
    """Set attention patches at specific UNet block indices."""
    # Input block indices for IP-Adapter
    input_block_indices = [4, 5, 7, 8]
    # Output block indices for IP-Adapter
    output_block_indices = list(range(6))

    def make_attn_patcher(ip_index):
        """Create a closure that patches a specific attention layer."""
        def patcher(attn2, extra_options):
            # Original attention
            q = extra_options["query"]
            k = extra_options["key"]
            v = extra_options["value"]

            # IP-Adapter K/V
            if ip_index < len(ip_kvs):
                ip_k, ip_v = ip_kvs[ip_index]
                ip_k = ip_k.to(k.device, k.dtype)
                ip_v = ip_v.to(v.device, v.dtype)

                # Concatenate original and IP K/V
                k = torch.cat([k, ip_k], dim=-2)
                v = torch.cat([v, ip_v], dim=-2)

            # Run attention
            return sdp(q, k, v, extra_options)

        return patcher

    # Register patches for input blocks
    for i, block_idx in enumerate(input_block_indices):
        for sub_idx in range(2 if block_idx < 6 else 10):
            ip_idx = i * 10 + sub_idx if i < 2 else i * 10 + sub_idx
            if ip_idx < len(ip_kvs):
                model.set_model_patch_replace(
                    make_attn_patcher(ip_idx),
                    "attn2",
                    ("input", block_idx, sub_idx),
                )

    # Register patches for output blocks
    for block_idx in output_block_indices:
        for sub_idx in range(10):
            ip_idx = 24 + block_idx * 10 + sub_idx
            if ip_idx < len(ip_kvs):
                model.set_model_patch_replace(
                    make_attn_patcher(ip_idx),
                    "attn2",
                    ("output", block_idx, sub_idx),
                )

    # Middle block patches (10 indices)
    for sub_idx in range(10):
        ip_idx = 84 + sub_idx
        if ip_idx < len(ip_kvs):
            model.set_model_patch_replace(
                make_attn_patcher(ip_idx),
                "attn2",
                ("middle", 0, sub_idx),
            )
