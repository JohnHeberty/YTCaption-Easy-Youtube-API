"""
SE8 Image Engine — StableDiffusionModel

Encapsulates UNet, VAE, CLIP, CLIP Vision and manages LoRA loading.

Design decisions:
- No global state — all state is instance-level
- Uses SE8 ModelPatcher instead of ldm_patched.modules.model_patcher
- Uses SE8 checkpoint module for load_model()
- Clean type hints, docstrings
"""

from __future__ import annotations
from common.log_utils import get_logger

import os
from typing import Any

logger = get_logger(__name__)


class StableDiffusionModel:
    """Encapsulates a loaded SD model with its components and LoRA state.

    Attributes:
        unet: ModelPatcher wrapping the UNet.
        vae: VAE wrapper for encode/decode.
        clip: CLIP wrapper for text encoding.
        clip_vision: CLIP Vision model (optional).
        filename: Path to the checkpoint file.
        vae_filename: Path to the VAE file (optional).
        unet_with_lora: UNet clone with LoRA patches applied.
        clip_with_lora: CLIP clone with LoRA patches applied.
        lora_key_map_unet: Mapping from LoRA keys to UNet state_dict keys.
        lora_key_map_clip: Mapping from LoRA keys to CLIP state_dict keys.
        visited_loras: String representation of last-applied LoRA config (cache key).
    """

    def __init__(
        self,
        unet=None,
        vae=None,
        clip=None,
        clip_vision=None,
        filename: str | None = None,
        vae_filename: str | None = None,
    ) -> None:
        self.unet = unet
        self.vae = vae
        self.clip = clip
        self.clip_vision = clip_vision
        self.filename = filename
        self.vae_filename = vae_filename

        # LoRA-augmented clones
        self.unet_with_lora = unet
        self.clip_with_lora = clip

        # LoRA cache
        self.visited_loras: str = ''

        # Key maps for LoRA matching
        self.lora_key_map_unet: dict[str, str] = {}
        self.lora_key_map_clip: dict[str, str] = {}

        self._init_lora_key_maps()

    def _init_lora_key_maps(self) -> None:
        """Initialize LoRA key maps from model state dicts."""
        try:
            from ldm_patched.modules.lora import model_lora_keys_unet, model_lora_keys_clip
        except ImportError:
            logger.warning("Could not import lora key functions — LoRA matching will be limited")
            return

        if self.unet is not None:
            try:
                self.lora_key_map_unet = model_lora_keys_unet(
                    self.unet.model, self.lora_key_map_unet
                )
                self.lora_key_map_unet.update(
                    {x: x for x in self.unet.model.state_dict().keys()}
                )
            except (RuntimeError, ValueError) as e:
                logger.warning(f"Failed to build UNet LoRA key map: {e}")

        if self.clip is not None and hasattr(self.clip, 'cond_stage_model') and self.clip.cond_stage_model is not None:
            try:
                self.lora_key_map_clip = model_lora_keys_clip(
                    self.clip.cond_stage_model, self.lora_key_map_clip
                )
                self.lora_key_map_clip.update(
                    {x: x for x in self.clip.cond_stage_model.state_dict().keys()}
                )
            except (RuntimeError, ValueError) as e:
                logger.warning(f"Failed to build CLIP LoRA key map: {e}")

    @property
    def has_unet(self) -> bool:
        return self.unet is not None

    @property
    def has_clip(self) -> bool:
        return self.clip is not None

    @property
    def has_vae(self) -> bool:
        return self.vae is not None

    def refresh_loras(self, loras: list[tuple[str, float]]) -> None:
        """Load and apply LoRA weights to this model.

        Uses visited_loras cache to skip reload if config hasn't changed.

        Args:
            loras: List of (filename, weight) tuples. filename 'None' skips.
        """
        import torch

        if not isinstance(loras, list):
            raise TypeError(f"loras must be a list, got {type(loras)}")

        # Cache check
        loras_str = str(loras)
        print(f"DEBUG refresh_loras: unet={'loaded' if self.unet else 'None'}, filename={self.filename}, cache={self.visited_loras[:30] if self.visited_loras else 'empty'}, loras={loras_str[:60]}")
        if self.visited_loras == loras_str:
            print(f"DEBUG refresh_loras: cache HIT, skipping")
            return

        self.visited_loras = loras_str

        if self.unet is None:
            print(f"DEBUG refresh_loras: unet is None, skipping")
            return

        logger.info(f"Loading LoRAs {loras_str} for model [{self.filename}]")

        # Resolve LoRA file paths
        loras_to_load = []
        for filename, weight in loras:
            if filename == 'None':
                continue

            if os.path.exists(filename):
                lora_filename = filename
            else:
                lora_filename = self._resolve_lora_path(filename)

            if lora_filename is None or not os.path.exists(lora_filename):
                logger.warning(f"LoRA file not found: {lora_filename}")
                continue

            loras_to_load.append((lora_filename, weight))

        if not loras_to_load:
            return

        print(f"DEBUG refresh_loras: loading {len(loras_to_load)} LoRAs")

        # Clone models for LoRA patching
        self.unet_with_lora = self.unet.clone() if self.unet is not None else None
        self.clip_with_lora = self.clip.clone() if self.clip is not None else None

        # Load each LoRA
        for lora_filename, weight in loras_to_load:
            self._apply_single_lora(lora_filename, weight)

    def _resolve_lora_path(self, name: str) -> str | None:
        """Resolve a LoRA name to a file path using config paths."""
        try:
            from modules.config import paths_loras
            from modules.util import get_file_from_folder_list
            return get_file_from_folder_list(name, paths_loras)
        except ImportError:
            # Fallback: try common paths
            for base in ['models/loras', 'data/models/loras']:
                path = os.path.join(base, name)
                if os.path.exists(path):
                    return path
                # Try with .safetensors extension
                if not name.endswith(('.safetensors', '.ckpt', '.pt')):
                    path = path + '.safetensors'
                    if os.path.exists(path):
                        return path
            return None

    def _apply_single_lora(self, lora_filename: str, weight: float) -> None:
        """Load a single LoRA file and apply to UNet and CLIP."""
        import torch
        from ldm_patched.modules.utils import load_torch_file

        print(f"DEBUG _apply_single_lora: {lora_filename}, weight={weight}")
        lora_data = load_torch_file(lora_filename, safe_load=False)

        # Direct matching: build model_key -> lora_prefix mapping from state_dict
        unet_patches = {}
        clip_patches = {}

        if self.unet is not None and hasattr(self.unet, 'model'):
            sdk = list(self.unet.model.state_dict().keys())
            diffusion_keys = [k for k in sdk if k.startswith("diffusion_model.") and k.endswith(".weight")]
            print(f"DEBUG UNet state_dict: {len(sdk)} total keys, {len(diffusion_keys)} diffusion_model.*.weight keys")
            if diffusion_keys:
                print(f"DEBUG UNet first diffusion key: {diffusion_keys[0]}")
            else:
                print(f"DEBUG UNet first 5 keys: {sdk[:5]}")
            for k in self.unet.model.state_dict().keys():
                if k.startswith("diffusion_model.") and k.endswith(".weight"):
                    lora_prefix = "lora_unet_" + k[len("diffusion_model."):-len(".weight")].replace(".", "_")
                    up_key = lora_prefix + ".lora_up.weight"
                    down_key = lora_prefix + ".lora_down.weight"
                    alpha_key = lora_prefix + ".alpha"
                    if up_key in lora_data and down_key in lora_data:
                        alpha = lora_data[alpha_key].item() if alpha_key in lora_data else None
                        unet_patches[k] = ("lora", (lora_data[up_key], lora_data[down_key], alpha, None))

        if self.clip is not None and hasattr(self.clip, 'cond_stage_model') and self.clip.cond_stage_model is not None:
            for k in self.clip.cond_stage_model.state_dict().keys():
                if k.endswith(".weight"):
                    lora_prefix = "lora_clip_" + k.replace(".", "_")
                    up_key = lora_prefix + ".lora_up.weight"
                    down_key = lora_prefix + ".lora_down.weight"
                    alpha_key = lora_prefix + ".alpha"
                    if up_key in lora_data and down_key in lora_data:
                        alpha = lora_data[alpha_key].item() if alpha_key in lora_data else None
                        clip_patches[k] = ("lora", (lora_data[up_key], lora_data[down_key], alpha, None))

        total = len(unet_patches) + len(clip_patches)
        if total == 0:
            print(f"DEBUG LoRA [{lora_filename}]: 0 keys matched, skipping")
            return

        print(f"DEBUG LoRA [{lora_filename}]: {total} keys matched (unet={len(unet_patches)}, clip={len(clip_patches)}), weight={weight}")

        if self.unet_with_lora is not None and unet_patches:
            loaded = self.unet_with_lora.add_patches(unet_patches, weight)
            print(f"DEBUG LoRA [{lora_filename}] → UNet: {len(loaded)} keys applied")

        if self.clip_with_lora is not None and clip_patches:
            loaded = self.clip_with_lora.add_patches(clip_patches, weight)
            print(f"DEBUG LoRA [{lora_filename}] → CLIP: {len(loaded)} keys applied")

    def __repr__(self) -> str:
        parts = [f"StableDiffusionModel(filename={self.filename!r}"]
        if self.vae_filename:
            parts.append(f"vae={self.vae_filename!r}")
        parts.append(f"unet={'yes' if self.unet else 'no'}")
        parts.append(f"clip={'yes' if self.clip else 'no'}")
        parts.append(f"vae={'yes' if self.vae else 'no'}")
        return ", ".join(parts) + ")"
