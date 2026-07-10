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

    import numpy as np
    import torch
    from PIL import Image
    import io

    # Decode image bytes -> numpy RGB
    if isinstance(img_data, bytes):
        img = np.array(Image.open(io.BytesIO(img_data)).convert("RGB"))
    elif isinstance(img_data, np.ndarray):
        img = img_data
    else:
        logger.warning("Inpaint: unexpected image type %s", type(img_data))
        return tasks, {}

    # Decode mask bytes -> numpy grayscale (255=masked, 0=keep)
    if isinstance(mask_data, bytes):
        mask = np.array(Image.open(io.BytesIO(mask_data)).convert("L"))
    elif isinstance(mask_data, np.ndarray):
        mask = mask_data
    else:
        logger.warning("Inpaint: unexpected mask type %s", type(mask_data))
        return tasks, {}

    if mask.ndim == 3:
        mask = mask[:, :, 0]

    # V2: invert mask if requested
    if async_task.invert_mask_checkbox:
        mask = 255 - mask
        logger.info("Inpaint: mask inverted (invert_mask_checkbox=True)")

    # Ensure mask is binary (255=masked, 0=keep)
    mask = (mask > 127).astype(np.uint8) * 255

    # Apply erode_or_dilate if requested
    erode_dilate = async_task.inpaint_erode_or_dilate or 0
    if erode_dilate != 0:
        from modules.util import erode_or_dilate
        mask = erode_or_dilate(mask, erode_dilate)
        logger.info("Inpaint mask erode_or_dilate=%d applied", erode_dilate)

    # Create InpaintWorker from modules (legacy, correct implementation)
    import modules.inpaint_worker as miw
    k = async_task.inpaint_respective_field or 0.618
    strength = async_task.inpaint_strength or 1.0
    use_fill = strength > 0.99
    worker = miw.InpaintWorker(img, mask, use_fill=use_fill, k=k)

    # Override task dimensions to match crop size
    crop_h, crop_w = worker.interested_image.shape[:2]
    for task in tasks:
        task["width"] = crop_w
        task["height"] = crop_h

    logger.warning(
        "InpaintWorker created: crop=%dx%d, k=%.3f, strength=%.2f",
        crop_w, crop_h, k, async_task.inpaint_strength,
    )

    # --- FULL INPAINT: Encode VAE latent + patch UNet ---
    inpaint_latent = None
    inpaint_latent_mask = None

    vae = getattr(pipeline, "final_vae", None) if pipeline is not None else None
    if vae is None:
        logger.warning("Inpaint: pipeline.final_vae not available, running as text-to-image only")
        return tasks, {
            "mode": "inpaint",
            "worker": worker,
            "prompt": async_task.inpaint_additional_prompt or "",
            "negative": getattr(async_task, "inpaint_negative_prompt", None),
            "strength": async_task.inpaint_strength,
        }

    try:
        import ldm_patched.modules.model_management

        device = ldm_patched.modules.model_management.get_torch_device()

        # Convert interested_fill (HWC uint8) to tensor [1, C, H, W] float [0,1]
        fill_np = worker.interested_fill.astype(np.float32) / 255.0
        fill_tensor = torch.tensor(fill_np, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)

        # Convert interested_mask to tensor [1, 1, H, W] float [0,1]
        mask_np = (worker.interested_mask > 0.5).astype(np.float32) if worker.interested_mask.max() <= 1.0 else worker.interested_mask.astype(np.float32) / 255.0
        mask_tensor = torch.tensor(mask_np, dtype=torch.float32).unsqueeze(0)
        mask_chw = mask_tensor.unsqueeze(1)  # [1, 1, H, W]

        # Apply mask blending: masked region -> 0.5 (gray), unmasked -> original
        blended = fill_tensor * (1 - mask_chw) + 0.5 * mask_chw

        # Move to GPU
        blended = blended.to(device=device)
        mask_tensor = mask_tensor.to(device=device)

        # Encode blended image to latent via VAE
        latent = None
        with torch.inference_mode():
            latent = vae.encode(blended)  # [1, 4, h, w]

        # Create latent-space mask
        B, C, H, W = latent.shape
        mask_for_latent = mask_tensor.unsqueeze(1)  # [1, 1, H_orig, W_orig]
        latent_mask = torch.nn.functional.interpolate(
            mask_for_latent, size=(H * 8, W * 8), mode="bilinear"
        ).round()
        latent_mask = torch.nn.functional.max_pool2d(
            latent_mask, (8, 8)
        ).round().to(latent.device, latent.dtype)  # [1, 1, H, W]

        # Store latent in InpaintWorker for sampler access
        worker.load_latent(latent, latent_mask)

        # Set global current_task -> activates patched_KSamplerX0Inpaint_forward
        miw.current_task = worker

        inpaint_latent = latent
        inpaint_latent_mask = latent_mask

        logger.warning(
            "Inpaint VAE encoded: latent shape=%s, mask shape=%s",
            list(latent.shape), list(latent_mask.shape),
        )

        # CUDA memory cleanup
        del fill_tensor, mask_tensor, blended
        try:
            import torch.cuda
            torch.cuda.ipc_collect()
        except Exception:
            pass

        # Patch UNet with InpaintHead CNN
        inpaint_head_path = None
        try:
            from modules.config import path_inpaint
            inpaint_head_path = os.path.join(path_inpaint, "fooocus_inpaint_head.pth")
        except ImportError:
            pass

        if inpaint_head_path and os.path.exists(inpaint_head_path):
            model = getattr(pipeline, "final_unet", None)
            if model is not None:
                patched_model = worker.patch(inpaint_head_path, latent, latent_mask, model)
                logger.warning("InpaintHead patched into UNet successfully")

                # Load inpaint patch model as LoRA (Fooocus pattern)
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
                    except Exception as dl_err:
                        logger.warning("Failed to download inpaint patch: %s", dl_err)

                if os.path.exists(inpaint_patch_path):
                    try:
                        import ldm_patched.modules.utils as _utils
                        from modules.core import match_lora

                        lora_data = _utils.load_torch_file(inpaint_patch_path, safe_load=False)

                        model_obj = pipeline.model_base
                        unet = model_obj.unet if model_obj else None
                        if unet is not None:
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
                        else:
                            logger.warning("Inpaint patch: UNet not available")
                        del lora_data
                        import gc; gc.collect()
                    except Exception as lora_err:
                        logger.warning("Failed to load inpaint patch LoRA: %s", lora_err)
                else:
                    logger.warning("Inpaint patch not found: %s", inpaint_patch_path)
            else:
                logger.warning("Inpaint: pipeline.final_unet not available for patching")
        else:
            # Try to download inpaint models
            try:
                from modules.config import downloading_inpaint_models
                downloading_inpaint_models(async_task.inpaint_engine or "v2.6")
                inpaint_head_path = os.path.join(path_inpaint, "fooocus_inpaint_head.pth")
                if os.path.exists(inpaint_head_path):
                    model = getattr(pipeline, "final_unet", None)
                    if model is not None:
                        patched_model = worker.patch(inpaint_head_path, latent, latent_mask, model)
                        logger.warning("InpaintHead downloaded and patched into UNet")
            except Exception as e:
                logger.warning("Failed to download/patch InpaintHead: %s", e)

    except Exception as e:
        logger.exception("Inpaint VAE encoding failed: %s", e)
        miw.current_task = None

    return tasks, {
        "mode": "inpaint",
        "worker": worker,
        "prompt": async_task.inpaint_additional_prompt or "",
        "negative": getattr(async_task, "inpaint_negative_prompt", None),
        "strength": async_task.inpaint_strength,
        "inpaint_latent": inpaint_latent,
        "inpaint_latent_mask": inpaint_latent_mask,
    }
