"""IP-Adapter and FaceID integration for SE8 worker.

Extracted from worker.py to reduce God Module size.
"""
from __future__ import annotations

import base64
import io
from typing import Any

from common.log_utils import get_logger

logger = get_logger(__name__)


def _load_faceid_adapter(
    faceid_adapter_path: str,
    clip_vision_path: str,
    ip_negative_path: str,
    faceid_embeds: list,
    faceid_weight: float,
) -> list:
    """Load FaceID Plus v2 adapter and project InsightFace embedding to cross-attention conditioning.

    FaceID Plus v2 architecture:
      - image_proj: Linear(512→1024) + Perceiver Resampler → 4 × 2048-d tokens
      - ip_adapter: LoRA (q/k/v/out) + standard to_k_ip/to_v_ip

    Returns list of [(ip_conds, ip_unconds), stop, weight] for patch_model.
    """
    import torch
    import numpy as np
    from modules.ops import use_patched_ops
    from ldm_patched.modules.ops import manual_cast

    load_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    offload_device = torch.device("cpu")

    use_fp16 = True
    dtype = torch.float16 if use_fp16 else torch.float32

    ip_state_dict = torch.load(faceid_adapter_path, map_location="cpu", weights_only=True)
    cross_attention_dim = 2048

    from app.services.faceid_adapter import FaceIDProj, FaceIDIPAdapter

    with use_patched_ops(manual_cast):
        faceid_proj = FaceIDProj(ip_state_dict["image_proj"])
        faceid_proj = faceid_proj.to(offload_device, dtype=dtype)
        faceid_proj.eval()

        faceid_ip = FaceIDIPAdapter(ip_state_dict["ip_adapter"], cross_attention_dim)
        faceid_ip = faceid_ip.to(offload_device, dtype=dtype)
        faceid_ip.eval()

    try:
        from extras import ip_adapter as ip_adapter_mod
        if ip_adapter_mod.clip_vision is None:
            ip_adapter_mod.load_ip_adapter(clip_vision_path, ip_negative_path, "/dev/null")
        ip_negative = ip_adapter_mod.ip_negative
    except Exception:
        ip_negative = None

    embeds_np = np.array(faceid_embeds, dtype=np.float32)
    embeds_tensor = torch.from_numpy(embeds_np).to(offload_device, dtype=dtype)

    try:
        ldm_patched.modules.model_management.load_model_gpu(faceid_proj.patcher if hasattr(faceid_proj, 'patcher') else None)
    except Exception:
        pass

    with torch.no_grad():
        projected = faceid_proj(embeds_tensor)
        logger.info("FaceID: projected embedding → %s tokens", list(projected.shape))

    ip_conds = []
    for kv in faceid_ip(projected):
        ip_conds.append(kv.cpu())

    ip_unconds = []
    if ip_negative is not None:
        neg_embeds = torch.zeros(1, 512, dtype=dtype, device=offload_device)
        with torch.no_grad():
            neg_projected = faceid_proj(neg_embeds)
        for kv in faceid_ip(neg_projected):
            ip_unconds.append(kv.cpu())
    else:
        for c in ip_conds:
            ip_unconds.append(torch.zeros_like(c))

    faceid_stop = 0.5
    tasks = [[(ip_conds, ip_unconds), faceid_stop, faceid_weight]]
    return tasks


def _apply_ip_adapter(async_task, pipeline):
    """Apply IP-Adapter conditioning to the UNet.

    This wires the parsed cn_tasks into the actual IP-Adapter pipeline:
    1. Downloads IP-Adapter models (clip vision, negative, adapter weights)
    2. Loads models via extras/ip_adapter.py
    3. Preprocesses each reference image through CLIP vision
    4. Patches pipeline.final_unet with IP-Adapter attention patches
    """
    import numpy as np
    from PIL import Image

    cn_ip = async_task.cn_tasks.get("cn_ip", [])
    cn_ip_face = async_task.cn_tasks.get("cn_ip_face", [])
    all_ip = cn_ip + cn_ip_face

    logger.info("IP-Adapter: cn_ip=%d, cn_ip_face=%d, total=%d", len(cn_ip), len(cn_ip_face), len(all_ip))
    if not all_ip and not async_task.ip_adapter_faceid_embeds:
        return

    try:
        from extras import ip_adapter
    except ImportError as e:
        logger.warning("IP-Adapter imports failed: %s", e)
        return

    adapter_paths = {}
    import os
    from modules.config import path_clip_vision, path_controlnet

    _adapter_files = {
        "ip": {
            "clip": os.path.join(path_clip_vision, "clip_vision_vit_h.safetensors"),
            "neg": os.path.join(path_controlnet, "fooocus_ip_negative.safetensors"),
            "adapter": os.path.join(path_controlnet, "ip-adapter-plus_sdxl_vit-h.bin"),
        },
        "face": {
            "clip": os.path.join(path_clip_vision, "clip_vision_vit_h.safetensors"),
            "neg": os.path.join(path_controlnet, "fooocus_ip_negative.safetensors"),
            "adapter": os.path.join(path_controlnet, "ip-adapter-plus-face_sdxl_vit-h.bin"),
        },
        "faceid": {
            "clip": os.path.join(path_clip_vision, "clip_vision_vit_h.safetensors"),
            "neg": os.path.join(path_controlnet, "fooocus_ip_negative.safetensors"),
            "adapter": os.path.join(path_controlnet, "ip-adapter-faceid-plusv2_sdxl.bin"),
        },
    }

    for adapter_type in ("ip", "face", "faceid"):
        tasks_for_type = cn_ip if adapter_type == "ip" else cn_ip_face if adapter_type == "face" else []
        if adapter_type == "faceid" and not async_task.ip_adapter_faceid_embeds:
            continue
        if not tasks_for_type and adapter_type != "faceid":
            continue

        files = _adapter_files[adapter_type]
        missing = [f for f in files.values() if not os.path.exists(f)]
        if missing:
            logger.info("IP-Adapter: model files missing for type=%s: %s (fallback to face adapter)", adapter_type, missing)
            if adapter_type == "faceid":
                adapter_type = "face"
                files = _adapter_files["face"]
                missing = [f for f in files.values() if not os.path.exists(f)]
                if missing:
                    logger.warning("IP-Adapter: face adapter also missing: %s", missing)
                    continue
            else:
                continue

        try:
            ip_adapter.load_ip_adapter(files["clip"], files["neg"], files["adapter"])
            adapter_paths[adapter_type] = files["adapter"]
            logger.info("IP-Adapter loaded: type=%s", adapter_type)
        except Exception as e:
            logger.warning("IP-Adapter load failed for type=%s: %s", adapter_type, e)
            continue

    if not adapter_paths:
        return

    ip_tasks = []
    for img_data, stop, weight in all_ip:
        if not img_data:
            continue

        try:
            if isinstance(img_data, str):
                raw = img_data
                if "," in raw and raw.startswith("data:"):
                    raw = raw.split(",", 1)[1]
                missing = len(raw) % 4
                if missing:
                    raw += "=" * (4 - missing)
                img_bytes = base64.b64decode(raw)
            elif isinstance(img_data, bytes):
                img_bytes = img_data
            else:
                continue

            pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            pil_img = pil_img.resize((224, 224), Image.LANCZOS)
            img_np = np.array(pil_img).astype(np.float32)

            adapter_type = "ip"
            for orig_task in cn_ip:
                if orig_task[0] is img_data:
                    adapter_type = "ip"
                    break
            for orig_task in cn_ip_face:
                if orig_task[0] is img_data:
                    adapter_type = "face"
                    break

            adapter_path = adapter_paths.get(adapter_type) or adapter_paths.get("ip")
            if not adapter_path:
                continue

            ip_conds, ip_unconds = ip_adapter.preprocess(img_np, adapter_path)
            ip_tasks.append([(ip_conds, ip_unconds), stop, weight])
            logger.info("IP-Adapter preprocessed: type=%s stop=%.2f weight=%.2f",
                        adapter_type, stop, weight)

        except Exception as e:
            logger.warning("IP-Adapter preprocess failed: %s", e)
            continue

    faceid_embeds = async_task.ip_adapter_faceid_embeds
    if faceid_embeds and adapter_paths.get("faceid"):
        try:
            import torch
            faceid_weight = async_task.ip_adapter_faceid_weight
            logger.info("FaceID: processing embedding (dim=%d) with weight=%.2f",
                        len(faceid_embeds[0]) if faceid_embeds else 0, faceid_weight)

            faceid_path = adapter_paths["faceid"]
            faceid_tasks = _load_faceid_adapter(
                faceid_path,
                files["clip"], files["neg"],
                faceid_embeds, faceid_weight,
            )
            if faceid_tasks:
                ip_tasks.extend(faceid_tasks)
                logger.info("FaceID: %d conditioning tasks generated", len(faceid_tasks))
            else:
                logger.warning("FaceID: adapter produced no tasks")
        except Exception as e:
            logger.warning("FaceID processing failed: %s", e, exc_info=True)

    if not ip_tasks:
        logger.warning("IP-Adapter: no valid tasks after preprocessing")
        return

    try:
        pipeline.final_unet = ip_adapter.patch_model(pipeline.final_unet, ip_tasks)
        logger.info("IP-Adapter patched UNet: %d reference images applied", len(ip_tasks))
    except Exception as e:
        logger.warning("IP-Adapter patch_model failed: %s", e)
