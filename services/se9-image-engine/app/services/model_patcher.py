"""
SE9 Image Engine — Model Patcher

Wraps a model with load/offload support, LoRA patching, and transformer options.

Design decisions:
- Uses SE9 ModelManager instead of global model_management
- No circular imports (cast_to_device defined locally)
- Clean type hints
"""

from __future__ import annotations

import copy
import inspect
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _cast_to_device(tensor, device, dtype, copy=False):
    """Cast tensor to device and dtype with non-blocking where possible."""
    device_supports_cast = False
    if tensor.dtype in (float, type(float)):
        device_supports_cast = True
    elif tensor.dtype.__str__() in ('torch.float16', 'torch.bfloat16'):
        if hasattr(device, 'type') and device.type == 'cuda':
            device_supports_cast = True

    non_blocking = True
    if hasattr(device, 'type') and device.type == 'mps':
        non_blocking = False

    if device_supports_cast:
        if copy:
            if tensor.device == device:
                return tensor.to(dtype, copy=copy, non_blocking=non_blocking)
            return tensor.to(device, copy=copy, non_blocking=non_blocking).to(dtype, non_blocking=non_blocking)
        else:
            return tensor.to(device, non_blocking=non_blocking).to(dtype, non_blocking=non_blocking)
    else:
        return tensor.to(device, dtype, copy=copy, non_blocking=non_blocking)


def _module_size(module) -> int:
    """Calculate memory size of a module's parameters in bytes."""
    mem = 0
    sd = module.state_dict()
    for k in sd:
        t = sd[k]
        mem += t.nelement() * t.element_size()
    return mem


class ModelPatcher:
    """
    Wraps a model with load/offload support, weight patching (LoRA), and
    transformer option management.

    Supports clone() for independent patch sets sharing the same underlying model.
    """

    def __init__(
        self,
        model: Any,
        load_device: Any,
        offload_device: Any,
        size: int = 0,
        current_device: Any = None,
        weight_inplace_update: bool = False,
    ):
        self.size = size
        self.model = model
        self.patches: Dict[str, list] = {}
        self.backup: Dict[str, Any] = {}
        self.object_patches: Dict[str, Any] = {}
        self.object_patches_backup: Dict[str, Any] = {}
        self.model_options: Dict[str, Any] = {"transformer_options": {}}
        self.model_size()  # calculates self.size and self.model_keys
        self.load_device = load_device
        self.offload_device = offload_device
        self.current_device = current_device if current_device is not None else offload_device
        self.weight_inplace_update = weight_inplace_update

    def model_size(self) -> int:
        if self.size > 0:
            return self.size
        self.size = _module_size(self.model)
        self.model_keys = set(self.model.state_dict().keys())
        return self.size

    def clone(self) -> ModelPatcher:
        n = ModelPatcher(
            self.model,
            self.load_device,
            self.offload_device,
            self.size,
            self.current_device,
            weight_inplace_update=self.weight_inplace_update,
        )
        n.patches = {k: v[:] for k, v in self.patches.items()}
        n.object_patches = self.object_patches.copy()
        n.model_options = copy.deepcopy(self.model_options)
        n.model_keys = self.model_keys
        return n

    def is_clone(self, other) -> bool:
        if hasattr(other, 'model') and self.model is other.model:
            return True
        return False

    def memory_required(self, input_shape) -> int:
        return self.model.memory_required(input_shape=input_shape)

    # -------------------------------------------------------------------
    # Sampler configuration
    # -------------------------------------------------------------------

    def set_model_sampler_cfg_function(self, sampler_cfg_function, disable_cfg1_optimization=False):
        if len(inspect.signature(sampler_cfg_function).parameters) == 3:
            self.model_options["sampler_cfg_function"] = lambda args: sampler_cfg_function(
                args["cond"], args["uncond"], args["cond_scale"]
            )
        else:
            self.model_options["sampler_cfg_function"] = sampler_cfg_function
        if disable_cfg1_optimization:
            self.model_options["disable_cfg1_optimization"] = True

    def set_model_sampler_post_cfg_function(self, post_cfg_function, disable_cfg1_optimization=False):
        self.model_options["sampler_post_cfg_function"] = (
            self.model_options.get("sampler_post_cfg_function", []) + [post_cfg_function]
        )
        if disable_cfg1_optimization:
            self.model_options["disable_cfg1_optimization"] = True

    def set_model_unet_function_wrapper(self, unet_wrapper_function):
        self.model_options["model_function_wrapper"] = unet_wrapper_function

    # -------------------------------------------------------------------
    # Transformer patches
    # -------------------------------------------------------------------

    def set_model_patch(self, patch, name):
        to = self.model_options["transformer_options"]
        if "patches" not in to:
            to["patches"] = {}
        to["patches"][name] = to["patches"].get(name, []) + [patch]

    def set_model_patch_replace(self, patch, name, block_name, number, transformer_index=None):
        to = self.model_options["transformer_options"]
        if "patches_replace" not in to:
            to["patches_replace"] = {}
        if name not in to["patches_replace"]:
            to["patches_replace"][name] = {}
        block = (block_name, number, transformer_index) if transformer_index is not None else (block_name, number)
        to["patches_replace"][name][block] = patch

    def set_model_attn1_patch(self, patch):
        self.set_model_patch(patch, "attn1_patch")

    def set_model_attn2_patch(self, patch):
        self.set_model_patch(patch, "attn2_patch")

    def set_model_attn1_replace(self, patch, block_name, number, transformer_index=None):
        self.set_model_patch_replace(patch, "attn1", block_name, number, transformer_index)

    def set_model_attn2_replace(self, patch, block_name, number, transformer_index=None):
        self.set_model_patch_replace(patch, "attn2", block_name, number, transformer_index)

    def set_model_attn1_output_patch(self, patch):
        self.set_model_patch(patch, "attn1_output_patch")

    def set_model_attn2_output_patch(self, patch):
        self.set_model_patch(patch, "attn2_output_patch")

    def set_model_input_block_patch(self, patch):
        self.set_model_patch(patch, "input_block_patch")

    def set_model_input_block_patch_after_skip(self, patch):
        self.set_model_patch(patch, "input_block_patch_after_skip")

    def set_model_output_block_patch(self, patch):
        self.set_model_patch(patch, "output_block_patch")

    def add_object_patch(self, name, obj):
        self.object_patches[name] = obj

    # -------------------------------------------------------------------
    # Model operations
    # -------------------------------------------------------------------

    def model_patches_to(self, device):
        """Move all patch tensors to the given device."""
        to = self.model_options["transformer_options"]
        if "patches" in to:
            for name in to["patches"]:
                patch_list = to["patches"][name]
                for i in range(len(patch_list)):
                    if hasattr(patch_list[i], "to"):
                        patch_list[i] = patch_list[i].to(device)
        if "patches_replace" in to:
            for name in to["patches_replace"]:
                for k in to["patches_replace"][name]:
                    if hasattr(to["patches_replace"][name][k], "to"):
                        to["patches_replace"][name][k] = to["patches_replace"][name][k].to(device)
        if "model_function_wrapper" in self.model_options:
            wrap_func = self.model_options["model_function_wrapper"]
            if hasattr(wrap_func, "to"):
                self.model_options["model_function_wrapper"] = wrap_func.to(device)

    def model_dtype(self):
        if hasattr(self.model, "get_dtype"):
            return self.model.get_dtype()

    # -------------------------------------------------------------------
    # LoRA / weight patches
    # -------------------------------------------------------------------

    def add_patches(self, patches, strength_patch=1.0, strength_model=1.0) -> list:
        p = set()
        for k in patches:
            if k in self.model_keys:
                p.add(k)
                current_patches = self.patches.get(k, [])
                current_patches.append((strength_patch, patches[k], strength_model))
                self.patches[k] = current_patches
        return list(p)

    def get_key_patches(self, filter_prefix=None):
        model_sd = self.model_state_dict()
        result = {}
        for k in model_sd:
            if filter_prefix is not None and not k.startswith(filter_prefix):
                continue
            if k in self.patches:
                result[k] = [model_sd[k]] + self.patches[k]
            else:
                result[k] = (model_sd[k],)
        return result

    def model_state_dict(self, filter_prefix=None):
        sd = self.model.state_dict()
        if filter_prefix is not None:
            keys = list(sd.keys())
            for k in keys:
                if not k.startswith(filter_prefix):
                    sd.pop(k)
        return sd

    def patch_model(self, device_to=None, patch_weights=True):
        """Apply object patches and weight patches, optionally moving to device."""
        for k in self.object_patches:
            old = getattr(self.model, k)
            if k not in self.object_patches_backup:
                self.object_patches_backup[k] = old
            setattr(self.model, k, self.object_patches[k])

        if patch_weights:
            model_sd = self.model_state_dict()
            for key in self.patches:
                if key not in model_sd:
                    logger.warning("Could not patch key '%s' — not in model", key)
                    continue

                weight = model_sd[key]
                inplace_update = self.weight_inplace_update

                if key not in self.backup:
                    self.backup[key] = weight.to(device=self.offload_device, copy=inplace_update)

                if device_to is not None:
                    temp_weight = _cast_to_device(weight, device_to, float, copy=True)
                else:
                    temp_weight = weight.to(float, copy=True)

                out_weight = self._calculate_weight(self.patches[key], temp_weight, key).to(weight.dtype)

                if inplace_update:
                    self._copy_to_param(self.model, key, out_weight)
                else:
                    self._set_attr(self.model, key, out_weight)
                del temp_weight

            if device_to is not None:
                self.model.to(device_to)
                self.current_device = device_to

        return self.model

    def _calculate_weight(self, patches, weight, key):
        """Apply LoRA/LoKr/LoHa/GLoRA/Diff patches to a weight tensor."""
        for p in patches:
            alpha = p[0]
            v = p[1]
            strength_model = p[2]

            if strength_model != 1.0:
                weight *= strength_model

            if isinstance(v, list):
                v = (self._calculate_weight(v[1:], v[0].clone(), key),)

            if len(v) == 1:
                patch_type = "diff"
            elif len(v) == 2:
                patch_type = v[0]
                v = v[1]

            if patch_type == "diff":
                w1 = v[0]
                if alpha != 0.0:
                    if w1.shape != weight.shape:
                        logger.warning("SHAPE MISMATCH %s: %s != %s — weight not merged", key, w1.shape, weight.shape)
                    else:
                        weight += alpha * _cast_to_device(w1, weight.device, weight.dtype)

            elif patch_type == "lora":
                mat1 = _cast_to_device(v[0], weight.device, float)
                mat2 = _cast_to_device(v[1], weight.device, float)
                if v[2] is not None:
                    alpha *= v[2] / mat2.shape[0]
                if v[3] is not None:
                    mat3 = _cast_to_device(v[3], weight.device, float)
                    final_shape = [mat2.shape[1], mat2.shape[0], mat3.shape[2], mat3.shape[3]]
                    mat2 = torch.mm(
                        mat2.transpose(0, 1).flatten(start_dim=1),
                        mat3.transpose(0, 1).flatten(start_dim=1),
                    ).reshape(final_shape).transpose(0, 1)
                try:
                    weight += (alpha * torch.mm(
                        mat1.flatten(start_dim=1), mat2.flatten(start_dim=1)
                    )).reshape(weight.shape).type(weight.dtype)
                except Exception as e:
                    logger.error("LoRA patch error for key %s: %s", key, e)

            elif patch_type == "lokr":
                w1 = v[0]
                w2 = v[1]
                w1_a, w1_b = v[3], v[4]
                w2_a, w2_b = v[5], v[6]
                t2 = v[7]
                dim = None

                if w1 is None:
                    dim = w1_b.shape[0]
                    w1 = torch.mm(
                        _cast_to_device(w1_a, weight.device, float),
                        _cast_to_device(w1_b, weight.device, float),
                    )
                else:
                    w1 = _cast_to_device(w1, weight.device, float)

                if w2 is None:
                    dim = w2_b.shape[0]
                    if t2 is None:
                        w2 = torch.mm(
                            _cast_to_device(w2_a, weight.device, float),
                            _cast_to_device(w2_b, weight.device, float),
                        )
                    else:
                        w2 = torch.einsum(
                            'i j k l, j r, i p -> p r k l',
                            _cast_to_device(t2, weight.device, float),
                            _cast_to_device(w2_b, weight.device, float),
                            _cast_to_device(w2_a, weight.device, float),
                        )
                else:
                    w2 = _cast_to_device(w2, weight.device, float)

                if len(w2.shape) == 4:
                    w1 = w1.unsqueeze(2).unsqueeze(2)
                if v[2] is not None and dim is not None:
                    alpha *= v[2] / dim

                try:
                    weight += alpha * torch.kron(w1, w2).reshape(weight.shape).type(weight.dtype)
                except Exception as e:
                    logger.error("LoKr patch error for key %s: %s", key, e)

            elif patch_type == "loha":
                w1a, w1b = v[0], v[1]
                if v[2] is not None:
                    alpha *= v[2] / w1b.shape[0]
                w2a, w2b = v[3], v[4]

                if v[5] is not None:
                    t1, t2 = v[5], v[6]
                    m1 = torch.einsum(
                        'i j k l, j r, i p -> p r k l',
                        _cast_to_device(t1, weight.device, float),
                        _cast_to_device(w1b, weight.device, float),
                        _cast_to_device(w1a, weight.device, float),
                    )
                    m2 = torch.einsum(
                        'i j k l, j r, i p -> p r k l',
                        _cast_to_device(t2, weight.device, float),
                        _cast_to_device(w2b, weight.device, float),
                        _cast_to_device(w2a, weight.device, float),
                    )
                else:
                    m1 = torch.mm(
                        _cast_to_device(w1a, weight.device, float),
                        _cast_to_device(w1b, weight.device, float),
                    )
                    m2 = torch.mm(
                        _cast_to_device(w2a, weight.device, float),
                        _cast_to_device(w2b, weight.device, float),
                    )

                try:
                    weight += (alpha * m1 * m2).reshape(weight.shape).type(weight.dtype)
                except Exception as e:
                    logger.error("LoHa patch error for key %s: %s", key, e)

            elif patch_type == "glora":
                if v[4] is not None:
                    alpha *= v[4] / v[0].shape[0]

                a1 = _cast_to_device(v[0].flatten(start_dim=1), weight.device, float)
                a2 = _cast_to_device(v[1].flatten(start_dim=1), weight.device, float)
                b1 = _cast_to_device(v[2].flatten(start_dim=1), weight.device, float)
                b2 = _cast_to_device(v[3].flatten(start_dim=1), weight.device, float)

                weight += (
                    (torch.mm(b2, b1) + torch.mm(torch.mm(weight.flatten(start_dim=1), a2), a1)) * alpha
                ).reshape(weight.shape).type(weight.dtype)

            else:
                logger.warning("Unknown patch type '%s' for key '%s'", patch_type, key)

        return weight

    def unpatch_model(self, device_to=None):
        """Restore original weights from backup and optionally move to device."""
        keys = list(self.backup.keys())

        if self.weight_inplace_update:
            for k in keys:
                self._copy_to_param(self.model, k, self.backup[k])
        else:
            for k in keys:
                self._set_attr(self.model, k, self.backup[k])

        self.backup = {}

        if device_to is not None:
            self.model.to(device_to)
            self.current_device = device_to

        keys = list(self.object_patches_backup.keys())
        for k in keys:
            setattr(self.model, k, self.object_patches_backup[k])
        self.object_patches_backup = {}

    # -------------------------------------------------------------------
    # Utility helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _copy_to_param(model, key, value):
        """Copy value into model parameter (inplace)."""
        params = dict(model.named_parameters())
        buffers = dict(model.named_buffers())
        if key in params:
            params[key].data.copy_(value)
        elif key in buffers:
            buffers[key].data.copy_(value)

    @staticmethod
    def _set_attr(model, key, value):
        """Set attribute on model by dotted key path."""
        parts = key.split(".")
        obj = model
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], value)


# Lazy import for torch inside _calculate_weight
import torch  # noqa: E402 — needed for LoRA weight math
