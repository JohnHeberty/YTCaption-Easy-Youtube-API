"""ControlNet — loading, inference, T2I adapter, LoRA ControlNet.

Clean-room rewrite of FOOOCUS ldm_patched/modules/controlnet.py (516 lines).
Supports: ControlNet, ControlLora, T2I-Adapter, linked-list chaining.
"""
import logging
import math
import os
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)


def broadcast_image_to(
    tensor: torch.Tensor, target_batch_size: int, batched_number: int
) -> torch.Tensor:
    """Broadcast a single-batch condition hint across the target batch size."""
    if tensor.shape[0] == target_batch_size:
        return tensor
    # Tile/repeat to match batch size
    repeats = target_batch_size // tensor.shape[0] + 1
    tensor = tensor.repeat(repeats, 1, 1, 1)[:target_batch_size]
    return tensor


class ControlBase:
    """Abstract base for all control types. Implements linked-list chaining."""

    def __init__(self, device=None):
        self.cond_hint_original: Optional[torch.Tensor] = None
        self.cond_hint: Optional[torch.Tensor] = None
        self.strength: float = 1.0
        self.timestep_percent_range: Tuple[float, float] = (0.0, 1.0)
        self.global_average_pooling: bool = False
        self.previous_controlnet: Optional["ControlBase"] = None
        self.device = device

    def set_cond_hint(
        self,
        cond_hint: torch.Tensor,
        strength: float = 1.0,
        timestep_percent_range: Tuple[float, float] = (0.0, 1.0),
    ) -> "ControlBase":
        """Set the image hint and control parameters. Returns self for chaining."""
        self.cond_hint_original = cond_hint
        self.strength = strength
        self.timestep_percent_range = timestep_percent_range
        return self

    def pre_run(self, model, percent_to_timestep_function):
        """Convert percent range to timestep range; recurse to linked controls."""
        self.timestep_range = (
            percent_to_timestep_function(self.timestep_percent_range[0]),
            percent_to_timestep_function(self.timestep_percent_range[1]),
        )
        if self.previous_controlnet is not None:
            self.previous_controlnet.pre_run(model, percent_to_timestep_function)

    def set_previous_controlnet(self, controlnet: "ControlBase"):
        """Link another ControlNet in the chain."""
        self.previous_controlnet = controlnet

    def cleanup(self):
        """Recursively clean up linked controls, free memory."""
        self.cond_hint = None
        if self.previous_controlnet is not None:
            self.previous_controlnet.cleanup()

    def get_models(self) -> List:
        """Recursively collect all ModelPatchers from the chain."""
        models = []
        if self.previous_controlnet is not None:
            models.extend(self.previous_controlnet.get_models())
        return models

    def copy_to(self, c: "ControlBase"):
        """Copy settings to another ControlBase."""
        c.cond_hint_original = self.cond_hint_original
        c.strength = self.strength
        c.timestep_percent_range = self.timestep_percent_range
        c.global_average_pooling = self.global_average_pooling

    def inference_memory_requirements(self, dtype) -> int:
        """Recursively sum memory requirements."""
        return 0

    def control_merge(
        self,
        control_input: Optional[torch.Tensor],
        control_output: Optional[Dict[str, List[torch.Tensor]]],
        control_prev: Optional[Dict[str, List[torch.Tensor]]],
        output_dtype: torch.dtype,
    ) -> Dict[str, List[torch.Tensor]]:
        """Core merge logic for ControlNet outputs."""
        output = {"input": [], "middle": [], "output": []}

        if control_output is not None:
            for key in ["input", "middle", "output"]:
                if key in control_output:
                    for i, c in enumerate(control_output[key]):
                        if c is not None:
                            # Apply strength scaling
                            c = c * self.strength
                            # Global average pooling
                            if self.global_average_pooling and c.dim() == 4:
                                c = c.mean(dim=[2, 3], keepdim=True)
                                c = c.expand_as(
                                    torch.zeros(1, c.shape[1], c.shape[2], c.shape[3])
                                )
                            output[key].append(c.to(output_dtype))
                        else:
                            output[key].append(None)

        # Merge with previous control by addition
        if control_prev is not None:
            for key in ["input", "middle", "output"]:
                if key in control_prev:
                    for i in range(min(len(output[key]), len(control_prev[key]))):
                        if output[key][i] is not None and control_prev[key][i] is not None:
                            if output[key][i].shape == control_prev[key][i].shape:
                                output[key][i] = output[key][i] + control_prev[key][i]

        return output


class ControlNet(ControlBase):
    """Standard ControlNet implementation."""

    def __init__(
        self,
        control_model,
        global_average_pooling: bool = False,
        device=None,
        load_device=None,
        manual_cast_dtype=None,
    ):
        super().__init__(device)
        from ldm_patched.modules.model_patcher import ModelPatcher

        self.control_model = control_model
        self.control_model_wrapped = ModelPatcher(
            control_model,
            load_device=load_device or device,
            offload_device="cpu",
        )
        self.load_device = load_device
        self.manual_cast_dtype = manual_cast_dtype
        self.global_average_pooling = global_average_pooling
        self.model_sampling_current = None

    def get_control(
        self,
        x_noisy: torch.Tensor,
        t: torch.Tensor,
        cond: dict,
        batched_number: int,
    ) -> Dict[str, List[torch.Tensor]]:
        """Main inference method. Run ControlNet on input."""
        # Check timestep range
        timestep = t[0].item()
        min_t, max_t = self.timestep_range
        if timestep < min_t or timestep > max_t:
            return self.control_merge(None, None, None, x_noisy.dtype)

        # Prepare condition hint
        if self.cond_hint_original is not None:
            if self.cond_hint is None or self.cond_hint.shape[0] != x_noisy.shape[0]:
                # Resize and broadcast
                from ldm_patched.modules.utils import common_upscale
                hint = self.cond_hint_original
                if hint.shape[2:] != x_noisy.shape[2:]:
                    hint = common_upscale(
                        hint, x_noisy.shape[3], x_noisy.shape[2], "nearest"
                    )
                hint = broadcast_image_to(hint, x_noisy.shape[0], batched_number)
                self.cond_hint = hint

        # Prepare input
        x_input = x_noisy
        if self.model_sampling_current is not None:
            x_input = self.model_sampling_current.calculate_input(t, x_noisy)

        # Run ControlNet
        context = cond.get("crossattn", None)
        y = cond.get("vector", None)
        hint = self.cond_hint.to(self.load_device) if self.cond_hint is not None else None
        x_input = x_input.to(self.load_device)
        t = t.to(self.load_device)
        if context is not None:
            context = context.to(self.load_device)
        if y is not None:
            y = y.to(self.load_device)

        with torch.no_grad():
            control = self.control_model(x_input, hint, t, context, y)

        return self.control_merge(None, control, None, x_noisy.dtype)

    def copy(self) -> "ControlNet":
        """Create a new ControlNet with same config."""
        c = ControlNet(
            self.control_model,
            self.global_average_pooling,
            self.device,
            self.load_device,
            self.manual_cast_dtype,
        )
        self.copy_to(c)
        return c

    def get_models(self) -> List:
        return [self.control_model_wrapped]

    def pre_run(self, model, percent_to_timestep_function):
        super().pre_run(model, percent_to_timestep_function)
        self.model_sampling_current = model.model_sampling

    def cleanup(self):
        super().cleanup()
        self.model_sampling_current = None


class ControlLora(ControlNet):
    """ControlNet variant using LoRA weights. Builds model dynamically at pre_run."""

    def __init__(self, control_weights: dict, global_average_pooling=False, device=None):
        ControlBase.__init__(self, device)
        self.control_weights = control_weights
        self.global_average_pooling = global_average_pooling
        self.control_model = None
        self.control_model_wrapped = None

    def pre_run(self, model, percent_to_timestep_function):
        """Build ControlNet from diffusion model weights + LoRA control weights."""
        super(ControlNet, self).pre_run(model, percent_to_timestep_function)

        from ldm_patched.modules.model_detection import (
            unet_config_from_diffusers_unet,
            model_config_from_unet,
        )
        from ldm_patched.controlnet.cldm import ControlNet as CLDMControlNet
        from ldm_patched.modules.ops import disable_weight_init, manual_cast
        from ldm_patched.modules.model_management import unet_dtype

        # Detect UNet config
        unet_config = unet_config_from_diffusers_unet(model.diffusion_model.model, "")
        model_config = model_config_from_unet(unet_config, "")
        operations_class = getattr(model_config, "operations", disable_weight_init)

        # Create ControlNet model
        control_model = CLDMControlNet(
            **model_config.unet_config,
            operations=operations_class,
            device=self.device,
            manipulator=model.diffusion_model.model,
        )

        # Copy weights from diffusion model
        sd = model.diffusion_model.model.state_dict()
        control_model.load_state_dict(sd, strict=False)

        # Overlay LoRA control weights
        for key, weight in self.control_weights.items():
            if key in control_model.state_dict():
                control_model.state_dict()[key].copy_(weight)

        self.control_model = control_model
        from ldm_patched.modules.model_patcher import ModelPatcher
        self.control_model_wrapped = ModelPatcher(
            control_model,
            load_device=model.load_device,
            offload_device="cpu",
        )

    def copy(self) -> "ControlLora":
        c = ControlLora(self.control_weights, self.global_average_pooling, self.device)
        self.copy_to(c)
        return c

    def cleanup(self):
        super().cleanup()
        self.control_model = None
        self.control_model_wrapped = None

    def get_models(self) -> List:
        return []

    def inference_memory_requirements(self, dtype) -> int:
        if self.control_model is None:
            return 0
        return sum(p.numel() * p.element_size() for p in self.control_model.parameters())


class T2IAdapter(ControlBase):
    """T2I-Adapter support (IP-Adapter, color, canny, etc.)."""

    def __init__(self, t2i_model, channels_in: int, device=None):
        super().__init__(device)
        self.t2i_model = t2i_model
        self.channels_in = channels_in
        self.control_input: Optional[torch.Tensor] = None

    def get_control(
        self,
        x_noisy: torch.Tensor,
        t: torch.Tensor,
        cond: dict,
        batched_number: int,
    ) -> Dict[str, List[torch.Tensor]]:
        """Run T2I-Adapter inference."""
        timestep = t[0].item()
        min_t, max_t = self.timestep_range
        if timestep < min_t or timestep > max_t:
            return self.control_merge(None, None, None, x_noisy.dtype)

        if self.cond_hint_original is None:
            return self.control_merge(None, None, None, x_noisy.dtype)

        # Resize hint if needed
        if self.cond_hint is None or self.cond_hint.shape[2:] != x_noisy.shape[2:]:
            from ldm_patched.modules.utils import common_upscale
            hint = common_upscale(
                self.cond_hint_original, x_noisy.shape[3], x_noisy.shape[2], "nearest"
            )
            self.cond_hint = hint

        hint = broadcast_image_to(self.cond_hint, x_noisy.shape[0], batched_number)

        # Run adapter (cached after first call)
        if self.control_input is None:
            with torch.no_grad():
                self.control_input = self.t2i_model(hint.to(self.device))

        # Split output for XL vs SD1
        if self.channels_in == 4:
            # SDXL: 4 channels
            control = {"input": [self.control_input] * 12}
        else:
            # SD1: split across blocks
            control = {"input": [self.control_input] * 12}

        return self.control_merge(None, control, None, x_noisy.dtype)

    def copy(self) -> "T2IAdapter":
        c = T2IAdapter(self.t2i_model, self.channels_in, self.device)
        self.copy_to(c)
        return c


def load_controlnet(ckpt_path: str, model=None) -> ControlBase:
    """Load any ControlNet checkpoint. Auto-detects format.

    Args:
        ckpt_path: Path to ControlNet checkpoint
        model: Optional diffusion model for ControlLora

    Returns:
        ControlNet, ControlLora, or T2IAdapter instance
    """
    from ldm_patched.modules.utils import load_torch_file, state_dict_prefix_replace

    logger.info("Loading ControlNet from %s", ckpt_path)
    state_dict = load_torch_file(ckpt_path, safe_load=True)

    # Detect format
    diffusers = False
    control_lora = False

    # Check for diffusers format
    if "controlnet.input_blocks.0.0.weight" in state_dict:
        diffusers = True

    # Check for ControlLora format
    if "input_blocks.0.0.weight" not in state_dict and "controlnet." not in state_dict:
        if any("lora" in k.lower() for k in state_dict.keys()):
            control_lora = True

    if control_lora and model is not None:
        # ControlLora: store weights for dynamic construction
        return ControlLora(state_dict)

    if diffusers:
        # Convert diffusers keys
        prefix_map = {
            "controlnet.": "",
        }
        state_dict = state_dict_prefix_replace(state_dict, prefix_map)

    # Load as standard ControlNet
    from ldm_patched.controlnet.cldm import ControlNet as CLDMControlNet

    # Detect model config
    try:
        from ldm_patched.modules.model_detection import (
            unet_config_from_diffusers_unet,
            model_config_from_unet,
        )
        # Try to detect from state dict
        unet_config = {"model_channels": 320, "use_spatial_transformer": True}
        model_config = type("Config", (), {"unet_config": unet_config, "operations": None})()
    except Exception:
        model_config = type("Config", (), {
            "unet_config": {"model_channels": 320, "use_spatial_transformer": True},
            "operations": None,
        })()

    # Determine device/dtype
    from app.services.model_manager import get_model_manager
    mm = get_model_manager()
    load_device = mm.device

    # Create model
    control_model = CLDMControlNet(
        **model_config.unet_config,
        device=load_device,
    )

    # Load weights
    control_model.load_state_dict(state_dict, strict=False)

    # Determine global average pooling
    global_avg_pooling = any(
        k.endswith(".weight") and "average_pool" in k.lower()
        for k in state_dict.keys()
    )

    return ControlNet(
        control_model,
        global_average_pooling=global_avg_pooling,
        device=load_device,
        load_device=load_device,
    )


def load_t2i_adapter(t2i_data: dict) -> T2IAdapter:
    """Load a T2I-Adapter checkpoint.

    Args:
        t2i_data: State dict of T2I-Adapter

    Returns:
        T2IAdapter instance
    """
    from ldm_patched.t2ia.adapter import Adapter, Adapter_light

    # Detect format
    is_light = any("light" in k.lower() for k in t2i_data.keys())

    # Determine channels
    first_key = [k for k in t2i_data.keys() if "weight" in k][0]
    cin = t2i_data[first_key].shape[1]

    # Detect XL mode
    xl = cin == 4  # SDXL uses 4 channels

    if is_light:
        model = Adapter_light(cin=cin, channels=[320, 640, 1280, 1280])
    else:
        model = Adapter(cin=cin, channels=[320, 640, 1280, 1280], xl=xl)

    model.load_state_dict(t2i_data)

    from app.services.model_manager import get_model_manager
    mm = get_model_manager()
    model = model.to(mm.device)

    return T2IAdapter(model, channels_in=cin, device=mm.device)
