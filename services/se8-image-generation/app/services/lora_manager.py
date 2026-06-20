"""
SE8 Image Engine — LoRA Manager

Handles LoRA file matching, key mapping, and loading for UNet + CLIP.

Design decisions:
- Pure functions, no global state
- Uses SE8 StableDiffusionModel instead of core.StableDiffusionModel
- Lazy torch imports
"""

from __future__ import annotations
from common.log_utils import get_logger

import os
from typing import Any, Dict, List, Optional, Set, Tuple

logger = get_logger(__name__)


def match_lora(lora_data: Dict[str, Any], to_load: Dict[str, str]) -> Tuple[Dict, Dict]:
    """Match LoRA file keys to model state_dict keys.

    Supports: fooocus format, regular LoRA, diffusers LoRA, transformers LoRA,
    LoHa, LoKr, GLoRA, diff, and w_norm/b_norm.

    Args:
        lora_data: Loaded LoRA safetensors/tensor dict.
        to_load: Mapping from model key → LoRA key.

    Returns:
        (patch_dict, remaining_dict) — matched patches and unmatched LoRA keys.
    """
    patch_dict: Dict[str, Any] = {}
    loaded_keys: Set[str] = set()

    for model_key, lora_key in to_load.items():
        real_load_key = lora_key

        # === Fooocus LoRA format (direct key match) ===
        if real_load_key in lora_data:
            patch_dict[real_load_key] = ('fooocus', lora_data[real_load_key])
            loaded_keys.add(real_load_key)
            continue

        # === Alpha ===
        alpha_name = f"{model_key}.alpha"
        alpha = None
        if alpha_name in lora_data:
            alpha = lora_data[alpha_name].item()
            loaded_keys.add(alpha_name)

        # === Regular / Diffusers / Transformers LoRA ===
        regular_lora = f"{model_key}.lora_up.weight"
        diffusers_lora = f"{model_key}_lora.up.weight"
        transformers_lora = f"{model_key}.lora_linear_layer.up.weight"
        A_name = None

        if regular_lora in lora_data:
            A_name = regular_lora
            B_name = f"{model_key}.lora_down.weight"
            mid_name = f"{model_key}.lora_mid.weight"
        elif diffusers_lora in lora_data:
            A_name = diffusers_lora
            B_name = f"{model_key}_lora.down.weight"
            mid_name = None
        elif transformers_lora in lora_data:
            A_name = transformers_lora
            B_name = f"{model_key}.lora_linear_layer.down.weight"
            mid_name = None

        if A_name is not None:
            mid = None
            if mid_name is not None and mid_name in lora_data:
                mid = lora_data[mid_name]
                loaded_keys.add(mid_name)
            patch_dict[to_load[model_key]] = ("lora", (
                lora_data[A_name], lora_data[B_name], alpha, mid
            ))
            loaded_keys.add(A_name)
            loaded_keys.add(B_name)
            continue

        # === LoHa ===
        hada_w1_a = f"{model_key}.hada_w1_a"
        if hada_w1_a in lora_data:
            hada_w1_b = f"{model_key}.hada_w1_b"
            hada_w2_a = f"{model_key}.hada_w2_a"
            hada_w2_b = f"{model_key}.hada_w2_b"
            hada_t1_name = f"{model_key}.hada_t1"
            hada_t2_name = f"{model_key}.hada_t2"

            hada_t1 = None
            hada_t2 = None
            if hada_t1_name in lora_data:
                hada_t1 = lora_data[hada_t1_name]
                hada_t2 = lora_data[hada_t2_name]
                loaded_keys.add(hada_t1_name)
                loaded_keys.add(hada_t2_name)

            patch_dict[to_load[model_key]] = ("loha", (
                lora_data[hada_w1_a], lora_data[hada_w1_b], alpha,
                lora_data[hada_w2_a], lora_data[hada_w2_b],
                hada_t1, hada_t2
            ))
            loaded_keys.add(hada_w1_a)
            loaded_keys.add(hada_w1_b)
            loaded_keys.add(hada_w2_a)
            loaded_keys.add(hada_w2_b)
            continue

        # === LoKr ===
        lokr_w1_name = f"{model_key}.lokr_w1"
        lokr_w2_name = f"{model_key}.lokr_w2"
        lokr_w1_a_name = f"{model_key}.lokr_w1_a"
        lokr_w1_b_name = f"{model_key}.lokr_w1_b"
        lokr_t2_name = f"{model_key}.lokr_t2"
        lokr_w2_a_name = f"{model_key}.lokr_w2_a"
        lokr_w2_b_name = f"{model_key}.lokr_w2_b"

        lokr_w1 = lora_data.get(lokr_w1_name)
        lokr_w2 = lora_data.get(lokr_w2_name)
        lokr_w1_a = lora_data.get(lokr_w1_a_name)
        lokr_w1_b = lora_data.get(lokr_w1_b_name)
        lokr_w2_a = lora_data.get(lokr_w2_a_name)
        lokr_w2_b = lora_data.get(lokr_w2_b_name)
        lokr_t2 = lora_data.get(lokr_t2_name)

        for name in [lokr_w1_name, lokr_w2_name, lokr_w1_a_name, lokr_w1_b_name,
                     lokr_w2_a_name, lokr_w2_b_name, lokr_t2_name]:
            if name in lora_data:
                loaded_keys.add(name)

        if any(v is not None for v in [lokr_w1, lokr_w2, lokr_w1_a, lokr_w2_a]):
            patch_dict[to_load[model_key]] = ("lokr", (
                lokr_w1, lokr_w2, alpha, lokr_w1_a, lokr_w1_b,
                lokr_w2_a, lokr_w2_b, lokr_t2
            ))
            continue

        # === GLoRA ===
        a1_name = f"{model_key}.a1.weight"
        a2_name = f"{model_key}.a2.weight"
        b1_name = f"{model_key}.b1.weight"
        b2_name = f"{model_key}.b2.weight"
        if a1_name in lora_data:
            patch_dict[to_load[model_key]] = ("glora", (
                lora_data[a1_name], lora_data[a2_name],
                lora_data[b1_name], lora_data[b2_name], alpha
            ))
            for n in [a1_name, a2_name, b1_name, b2_name]:
                loaded_keys.add(n)
            continue

        # === Diff / w_norm + b_norm ===
        w_norm_name = f"{model_key}.w_norm"
        b_norm_name = f"{model_key}.b_norm"
        w_norm = lora_data.get(w_norm_name)
        b_norm = lora_data.get(b_norm_name)

        if w_norm is not None:
            loaded_keys.add(w_norm_name)
            patch_dict[to_load[model_key]] = ("diff", (w_norm,))
            if b_norm is not None:
                loaded_keys.add(b_norm_name)
                bias_key = f"{model_key[:-len('.weight')]}.bias" if model_key.endswith('.weight') else f"{model_key}.bias"
                patch_dict[bias_key] = ("diff", (b_norm,))

        diff_name = f"{model_key}.diff"
        diff_weight = lora_data.get(diff_name)
        if diff_weight is not None:
            patch_dict[to_load[model_key]] = ("diff", (diff_weight,))
            loaded_keys.add(diff_name)

        diff_bias_name = f"{model_key}.diff_b"
        diff_bias = lora_data.get(diff_bias_name)
        if diff_bias is not None:
            bias_key = f"{model_key[:-len('.weight')]}.bias" if model_key.endswith('.weight') else f"{model_key}.bias"
            patch_dict[bias_key] = ("diff", (diff_bias,))
            loaded_keys.add(diff_bias_name)

    remaining_dict = {k: v for k, v in lora_data.items() if k not in loaded_keys}
    return patch_dict, remaining_dict


def get_file_from_folder_list(name: str, folders: List[str]) -> Optional[str]:
    """Resolve a filename by searching through a list of folders.

    Args:
        name: Filename or relative path.
        folders: List of directories to search.

    Returns:
        Absolute path if found, None otherwise.
    """
    if os.path.exists(name):
        return name

    for folder in folders:
        if not isinstance(folder, str):
            continue
        full_path = os.path.join(folder, name)
        if os.path.exists(full_path):
            return full_path

        # Try common extensions
        for ext in ['.safetensors', '.ckpt', '.pt', '.pth']:
            if not name.endswith(ext):
                ext_path = full_path + ext
                if os.path.exists(ext_path):
                    return ext_path

    return None


def get_enabled_loras(loras: List[Dict[str, Any]]) -> List[Tuple[str, float]]:
    """Extract enabled LoRAs as (filename, weight) tuples.

    Args:
        loras: List of LoRA config dicts with 'enabled', 'model_name', 'weight' keys.

    Returns:
        List of (filename, weight) for enabled LoRAs only.
    """
    result = []
    for lora in loras:
        if isinstance(lora, dict):
            if lora.get('enabled', True):
                name = lora.get('model_name', 'None')
                weight = lora.get('weight', 0.5)
                result.append((name, weight))
        elif isinstance(lora, (list, tuple)) and len(lora) >= 2:
            name, weight = lora[0], lora[1]
            result.append((name, weight))
    return result


def refresh_loras_for_models(
    model_base,
    model_refiner,
    loras: List[Tuple[str, float]],
    base_model_additional_loras: Optional[List[Tuple[str, float]]] = None,
):
    """Refresh LoRAs for both base and refiner models.

    Args:
        model_base: StableDiffusionModel for base.
        model_refiner: StableDiffusionModel for refiner.
        loras: List of (filename, weight) tuples.
        base_model_additional_loras: Extra LoRAs for base only.
    """
    if not isinstance(base_model_additional_loras, list):
        base_model_additional_loras = []

    model_base.refresh_loras(loras + base_model_additional_loras)
    model_refiner.refresh_loras(loras)
