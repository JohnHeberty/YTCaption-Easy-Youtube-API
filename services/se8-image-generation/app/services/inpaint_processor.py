"""Inpaint pipeline — crop, VAE encode, UNet patch, LoRA load.

Extracted from worker.py (254 lines). Self-contained inpaint flow.
"""
from __future__ import annotations

import os
from typing import Any

from common.log_utils import get_logger

logger = get_logger(__name__)


def apply_inpaint(async_task, tasks: list, pipeline: Any = None) -> tuple[list, dict]:
    """Apply inpaint mode. Creates InpaintWorker, encodes VAE latent, patches UNet.

    Full Fooocus inpaint flow:
    1. Crop around mask with InpaintWorker
    2. Encode crop+mask to latent via VAE
    3. Set modules.inpaint_worker.current_task (activates sampler latent mixing)
    4. Patch UNet with InpaintHead (adds inpaint features to input block 0)
    """
    if not async_task.inpaint_input_image:
        return tasks, {}

    img_data = async_task.inpaint_input_image.get("image")
    mask_data = async_task.inpaint_input_image.get("mask")
    if not img_data or not mask_data:
        return tasks, {}

    img = _decode_input_image(img_data)
    if img is None:
        return tasks, {}

    mask = _decode_mask(mask_data, async_task)
    if mask is None:
        return tasks, {}

    mask = _preprocess_mask(mask, async_task)

    import modules.inpaint_worker as miw
    k = async_task.inpaint_respective_field or 0.618
    strength = async_task.inpaint_strength or 1.0
    use_fill = strength > 0.99
    worker = miw.InpaintWorker(img, mask, use_fill=use_fill, k=k)

    crop_h, crop_w = worker.interested_image.shape[:2]
    for task in tasks:
        task["width"] = crop_w
        task["height"] = crop_h

    logger.warning(
        "InpaintWorker created: crop=%dx%d, k=%.3f, strength=%.2f",
        crop_w, crop_h, k, async_task.inpaint_strength,
    )

    inpaint_latent, inpaint_latent_mask = _encode_inpaint_latent(
        async_task, worker, pipeline, miw
    )

    if inpaint_latent is not None:
        _patch_unet_inpaint(async_task, worker, inpaint_latent, inpaint_latent_mask, pipeline)

    return tasks, {
        "mode": "inpaint",
        "worker": worker,
        "prompt": async_task.inpaint_additional_prompt or "",
        "negative": getattr(async_task, "inpaint_negative_prompt", None),
        "strength": async_task.inpaint_strength,
        "inpaint_latent": inpaint_latent,
        "inpaint_latent_mask": inpaint_latent_mask,
    }


def _decode_input_image(img_data: Any) -> Any:
    """Decode image bytes/ndarray to numpy RGB array."""
    import numpy as np
    from PIL import Image
    import io

    if isinstance(img_data, bytes):
        return np.array(Image.open(io.BytesIO(img_data)).convert("RGB"))
    if isinstance(img_data, np.ndarray):
        return img_data
    logger.warning("Inpaint: unexpected image type %s", type(img_data))
    return None


def _decode_mask(mask_data: Any, async_task: Any) -> Any:
    """Decode mask bytes/ndarray to numpy grayscale array."""
    import numpy as np
    from PIL import Image
    import io

    if isinstance(mask_data, bytes):
        mask = np.array(Image.open(io.BytesIO(mask_data)).convert("L"))
    elif isinstance(mask_data, np.ndarray):
        mask = mask_data
    else:
        logger.warning("Inpaint: unexpected mask type %s", type(mask_data))
        return None

    if mask.ndim == 3:
        mask = mask[:, :, 0]
    return mask


def _preprocess_mask(mask: Any, async_task: Any) -> Any:
    """Apply inversion, binarization, and erode/dilate to mask."""
    import numpy as np

    if async_task.invert_mask_checkbox:
        mask = 255 - mask
        logger.info("Inpaint: mask inverted (invert_mask_checkbox=True)")

    mask = (mask > 127).astype(np.uint8) * 255

    erode_dilate = async_task.inpaint_erode_or_dilate or 0
    if erode_dilate != 0:
        from modules.util import erode_or_dilate
        mask = erode_or_dilate(mask, erode_dilate)
        logger.info("Inpaint mask erode_or_dilate=%d applied", erode_dilate)

    return mask


def _encode_inpaint_latent(
    async_task: Any, worker: Any, pipeline: Any, miw: Any
) -> tuple[Any, Any]:
    """Encode inpaint crop+mask to VAE latent and latent-space mask."""
    vae = getattr(pipeline, "final_vae", None) if pipeline is not None else None
    if vae is None:
        logger.warning("Inpaint: pipeline.final_vae not available, running as text-to-image only")
        return None, None

    try:
        import numpy as np
        import torch
        import ldm_patched.modules.model_management

        device = ldm_patched.modules.model_management.get_torch_device()

        fill_np = worker.interested_fill.astype(np.float32) / 255.0
        fill_tensor = torch.tensor(fill_np, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)

        mask_np = (worker.interested_mask > 0.5).astype(np.float32) if worker.interested_mask.max() <= 1.0 else worker.interested_mask.astype(np.float32) / 255.0
        mask_tensor = torch.tensor(mask_np, dtype=torch.float32).unsqueeze(0)
        mask_chw = mask_tensor.unsqueeze(1)

        blended = fill_tensor * (1 - mask_chw) + 0.5 * mask_chw

        blended = blended.to(device=device)
        mask_tensor = mask_tensor.to(device=device)

        with torch.inference_mode():
            latent = vae.encode(blended)

        B, C, H, W = latent.shape
        mask_for_latent = mask_tensor.unsqueeze(1)
        latent_mask = torch.nn.functional.interpolate(
            mask_for_latent, size=(H * 8, W * 8), mode="bilinear"
        ).round()
        latent_mask = torch.nn.functional.max_pool2d(
            latent_mask, (8, 8)
        ).round().to(latent.device, latent.dtype)

        worker.load_latent(latent, latent_mask)
        miw.current_task = worker

        logger.warning(
            "Inpaint VAE encoded: latent shape=%s, mask shape=%s",
            list(latent.shape), list(latent_mask.shape),
        )

        del fill_tensor, mask_tensor, blended
        try:
            import torch.cuda
            torch.cuda.ipc_collect()
        except (RuntimeError, OSError) as e:
            logger.debug("CUDA ipc_collect failed (non-fatal): %s", e)

        return latent, latent_mask

    except Exception as e:
        logger.exception("Inpaint VAE encoding failed: %s", e)
        miw.current_task = None
        return None, None


def _patch_unet_inpaint(
    async_task: Any, worker: Any, latent: Any, latent_mask: Any, pipeline: Any
) -> None:
    """Patch UNet with InpaintHead + inpaint LoRA patch."""
    inpaint_head_path = _resolve_inpaint_head_path()
    unet = getattr(pipeline, "final_unet", None) if pipeline is not None else None

    if inpaint_head_path and os.path.exists(inpaint_head_path) and unet is not None:
        _patch_head_and_lora(async_task, worker, latent, latent_mask, pipeline, inpaint_head_path)
    else:
        _try_download_and_patch(async_task, worker, latent, latent_mask, pipeline)


def _resolve_inpaint_head_path() -> str | None:
    """Resolve path to inpaint_head.pth."""
    try:
        from modules.config import path_inpaint
        return os.path.join(path_inpaint, "fooocus_inpaint_head.pth")
    except ImportError:
        return None


def _patch_head_and_lora(
    async_task: Any, worker: Any, latent: Any, latent_mask: Any, pipeline: Any, inpaint_head_path: str
) -> None:
    """Patch UNet with InpaintHead and load inpaint LoRA."""
    model = getattr(pipeline, "final_unet", None)
    if model is None:
        logger.warning("Inpaint: pipeline.final_unet not available for patching")
        return

    worker.patch(inpaint_head_path, latent, latent_mask, model)
    logger.warning("InpaintHead patched into UNet successfully")

    inpaint_patch_map = {
        "v1": "inpaint.fooocus.patch",
        "v2.5": "inpaint_v25.fooocus.patch",
        "v2.6": "inpaint_v26.fooocus.patch",
    }
    engine_ver = async_task.inpaint_engine or "v2.6"
    patch_name = inpaint_patch_map.get(engine_ver, inpaint_patch_map["v2.6"])
    inpaint_patch_path = os.path.join(os.path.dirname(inpaint_head_path), patch_name)

    if not os.path.exists(inpaint_patch_path):
        try:
            from modules.config import downloading_inpaint_models
            downloading_inpaint_models(engine_ver)
        except (OSError, ValueError) as dl_err:
            logger.warning("Failed to download inpaint patch: %s", dl_err)

    if os.path.exists(inpaint_patch_path):
        _load_inpaint_lora(inpaint_patch_path, patch_name, pipeline)
    else:
        logger.warning("Inpaint patch not found: %s", inpaint_patch_path)


def _load_inpaint_lora(inpaint_patch_path: str, patch_name: str, pipeline: Any) -> None:
    """Load inpaint patch LoRA into UNet."""
    try:
        import ldm_patched.modules.utils as _utils
        from modules.core import match_lora

        lora_data = _utils.load_torch_file(inpaint_patch_path, safe_load=False)

        model_obj = pipeline.model_base
        unet = model_obj.unet if model_obj else None
        if unet is None:
            logger.warning("Inpaint patch: UNet not available")
            return

        key_map_unet = {}
        for k in unet.model.state_dict().keys():
            if k.startswith("diffusion_model.") and k.endswith(".weight"):
                lora_key = k[len("diffusion_model."):-len(".weight")].replace(".", "_")
                key_map_unet[f"lora_unet_{lora_key}"] = k

        lora_unet, lora_unmatch = match_lora(lora_data, key_map_unet)
        total = len(lora_unet)
        if total > 0:
            if model_obj.unet_with_lora is None:
                model_obj.unet_with_lora = unet.clone()
            loaded = model_obj.unet_with_lora.add_patches(lora_unet, 1.0)
            logger.warning("Inpaint patch LoRA loaded: %s — %d keys at weight=1.0", patch_name, len(loaded))
        else:
            logger.warning("Inpaint patch LoRA: 0 keys matched for UNet")

        del lora_data
        import gc; gc.collect()
    except (RuntimeError, ValueError, OSError) as lora_err:
        logger.warning("Failed to load inpaint patch LoRA: %s", lora_err)


def _try_download_and_patch(
    async_task: Any, worker: Any, latent: Any, latent_mask: Any, pipeline: Any
) -> None:
    """Try downloading inpaint models and patching as fallback."""
    try:
        from modules.config import downloading_inpaint_models, path_inpaint
        downloading_inpaint_models(async_task.inpaint_engine or "v2.6")
        inpaint_head_path = os.path.join(path_inpaint, "fooocus_inpaint_head.pth")
        if os.path.exists(inpaint_head_path):
            model = getattr(pipeline, "final_unet", None)
            if model is not None:
                worker.patch(inpaint_head_path, latent, latent_mask, model)
                logger.warning("InpaintHead downloaded and patched into UNet")
    except (OSError, ValueError, RuntimeError) as e:
        logger.warning("Failed to download/patch InpaintHead: %s", e)
