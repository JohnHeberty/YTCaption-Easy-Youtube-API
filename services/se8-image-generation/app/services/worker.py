"""GPU worker for SE8 Image Engine.

Single-threaded GPU worker that processes image generation tasks.

Architecture:
- task_schedule_loop() runs in a thread, processes one task at a time
- process_generate() is the core function, decorated with @torch.no_grad()
- Each task goes through: image_input → prompt → vary/upscale/inpaint → diffusion → save
"""

from __future__ import annotations
from common.log_utils import get_logger

import base64
import io
import os
import time
from pathlib import Path
from typing import Any

from app.domain.task_models import (
    AsyncTask,
    GenerationFinishReason,
    ImageGenerationResult,
    QueueTask,
    TaskOutputs,
    TaskStatus,
    TaskType,
)
from app.services.task_queue import TaskQueue

logger = get_logger(__name__)

# Module-level state
worker_queue: TaskQueue | None = None
_last_model_name: str | None = None


def process_stop() -> None:
    """Interrupt current processing."""
    try:
        from app.services.model_manager import get_model_manager
        get_model_manager().interrupt_current_processing()
    except Exception as e:
        logger.warning("Failed to interrupt processing: %s", e)


def _detect_task_type(req: dict[str, Any]) -> TaskType:
    """Detect task type from request parameters."""
    current_tab = req.get("current_tab", "prompt")
    if current_tab == "uov" or req.get("uov_input_image"):
        return TaskType.IMG_UPSCALE_VARY
    if current_tab == "inpaint" or req.get("inpaint_input_image"):
        return TaskType.IMG_INPAINT_OUTPAINT
    if current_tab == "ip" or req.get("image_prompts"):
        return TaskType.IMG_PROMPT
    if current_tab == "enhance" or req.get("enhance_checkbox"):
        return TaskType.IMG_ENHANCE
    return TaskType.TEXT_TO_IMAGE


def _build_async_task(req: dict[str, Any]) -> AsyncTask:
    """Build AsyncTask from request parameters."""
    advanced = req.get("advanced_params") or {}
    if isinstance(advanced, dict):
        adv = advanced
    else:
        adv = getattr(advanced, "__dict__", {})

    return AsyncTask(
        prompt=req.get("prompt", ""),
        negative_prompt=req.get("negative_prompt", ""),
        style_selections=req.get("style_selections", []),
        performance_selection=req.get("performance_selection", "Speed"),
        aspect_ratios_selection=req.get("aspect_ratios_selection", "1024×1024"),
        image_number=req.get("image_number", 1),
        output_format=req.get("output_format", "png"),
        seed=str(req.get("image_seed", "")),
        read_wildcards_in_order=req.get("read_wildcards_in_order", False),
        sharpness=req.get("sharpness", 2.0),
        guidance_scale=req.get("guidance_scale", 4.0),
        base_model_name=req.get("base_model_name", ""),
        refiner_model_name=req.get("refiner_model_name", ""),
        refiner_switch=req.get("refiner_switch", 0.5),
        loras=req.get("loras", []),
        uov_method=req.get("uov_method"),
        uov_input_image=req.get("uov_input_image"),
        upscale_value=req.get("upscale_value"),
        outpaint_selections=req.get("outpaint_selections", []),
        inpaint_input_image=req.get("inpaint_input_image"),
        inpaint_additional_prompt=req.get("inpaint_additional_prompt"),
        inpaint_mask_image_upload=req.get("inpaint_mask_image_upload"),
        current_tab=req.get("current_tab", "prompt"),
        input_image_checkbox=bool(req.get("uov_input_image") or req.get("inpaint_input_image")),
        enhance_input_image=req.get("enhance_input_image"),
        enhance_checkbox=req.get("enhance_checkbox", False),
        enhance_uov_method=req.get("enhance_uov_method"),
        enhance_uov_processing_order=req.get("enhance_uov_processing_order", "Before First Enhancement"),
        enhance_uov_prompt_type=req.get("enhance_uov_prompt_type", "Same to Detailed Prompt"),
        enhance_ctrlnets=req.get("enhance_ctrlnets", []),
        image_prompts=req.get("image_prompts", []),
        cn_tasks=req.get("cn_tasks", {}),
        disable_preview=adv.get("disable_preview", False),
        disable_intermediate_results=adv.get("disable_intermediate_results", False),
        disable_seed_increment=adv.get("disable_seed_increment", False),
        black_out_nsfw=adv.get("black_out_nsfw", False),
        adm_scaler_positive=adv.get("adm_scaler_positive", 1.5),
        adm_scaler_negative=adv.get("adm_scaler_negative", 0.8),
        adm_scaler_end=adv.get("adm_scaler_end", 0.3),
        adaptive_cfg=adv.get("adaptive_cfg", 7.0),
        clip_skip=adv.get("clip_skip", 2),
        sampler_name=adv.get("sampler_name", "dpmpp_2m_ssd_gpu"),
        scheduler_name=adv.get("scheduler_name", "karras"),
        vae_name=adv.get("vae_name"),
        overwrite_step=adv.get("overwrite_step", -1),
        overwrite_switch=adv.get("overwrite_switch", -1),
        overwrite_width=adv.get("overwrite_width", -1),
        overwrite_height=adv.get("overwrite_height", -1),
        overwrite_vary_strength=adv.get("overwrite_vary_strength", -1),
        refiner_swap_method=adv.get("refiner_swap_method", "joint"),
        controlnet_softness=adv.get("controlnet_softness", 0.25),
        freeu_enabled=adv.get("freeu_enabled", False),
        freeu_b1=adv.get("freeu_b1", 1.01),
        freeu_b2=adv.get("freeu_b2", 1.02),
        freeu_s1=adv.get("freeu_s1", 0.99),
        freeu_s2=adv.get("freeu_s2", 0.95),
        inpaint_engine=adv.get("inpaint_engine", "v2.6"),
        inpaint_strength=adv.get("inpaint_strength", 1.0),
        inpaint_respective_field=adv.get("inpaint_respective_field", 0.5),
        inpaint_erode_or_dilate=adv.get("inpaint_erode_or_dilate", 0),
        inpaint_disable_initial_latent=adv.get("inpaint_disable_initial_latent", False),
        save_metadata_to_images=adv.get("save_metadata_to_images", False),
        metadata_scheme=adv.get("metadata_scheme", "fooocus"),
        save_final_enhanced_image_only=req.get("save_final_enhanced_image_only", True),
        require_base64=req.get("require_base64", False),
        webhook_url=req.get("webhook_url"),
        outpaint_distance_left=req.get("outpaint_distance_left", 0),
        outpaint_distance_top=req.get("outpaint_distance_top", 0),
        outpaint_distance_right=req.get("outpaint_distance_right", 0),
        outpaint_distance_bottom=req.get("outpaint_distance_bottom", 0),
        # V2: invert mask + FaceID
        invert_mask_checkbox=adv.get("invert_mask_checkbox", False),
        ip_adapter_faceid_embeds=req.get("ip_adapter_faceid_embeds"),
        ip_adapter_faceid_weight=req.get("ip_adapter_faceid_weight", 0.8),
    )


def _save_output_file(
    img,
    output_dir: str = "",
    subfolder: str = "",
    filename: str | None = None,
) -> str:
    """Save a PIL/numpy image to the outputs directory. Returns the file path."""
    import numpy as np

    if not output_dir:
        from app.core.config import get_settings
        output_dir = get_settings().output_dir

    # Convert to numpy if needed
    if hasattr(img, "save"):
        # PIL Image
        img_array = np.array(img)
    elif isinstance(img, np.ndarray):
        img_array = img
    else:
        img_array = np.array(img)

    # Build output path
    from datetime import datetime
    now = datetime.now()
    date_folder = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d_%H-%M-%S")

    if not filename:
        filename = f"{time_str}.png"

    out_dir = Path(output_dir) / date_folder
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    # Save via PIL
    try:
        from PIL import Image as PILImage
        pil_img = PILImage.fromarray(img_array.astype(np.uint8) if img_array.dtype != np.uint8 else img_array)
        pil_img.save(str(out_path))
    except ImportError:
        # Fallback: save as raw PNG using cv2 if available
        import cv2
        cv2.imwrite(str(out_path), cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR))

    return str(out_path)


def _save_and_log(
    async_task: AsyncTask,
    imgs: list,
    loras: list,
    use_expansion: bool,
    width: int,
    height: int,
    persist_image: bool = True,
) -> list[str]:
    """Save images and log metadata. Returns list of file paths."""
    import numpy as np
    from datetime import datetime

    img_paths = []
    metadata_lines = [
        f"Prompt: {async_task.prompt}",
        f"Negative: {async_task.negative_prompt}",
        f"Style: {async_task.style_selections}",
        f"Performance: {async_task.performance_selection}",
        f"Size: {width}×{height}",
        f"Model: {async_task.base_model_name}",
        f"LoRAs: {loras}",
    ]

    for i, img in enumerate(imgs):
        if isinstance(img, str):
            # Already a file path
            img_paths.append(img)
            continue

        seed = async_task.seed if i == 0 else str(int(async_task.seed) + i) if async_task.seed.isdigit() else async_task.seed
        filename = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{seed}.png"
        path = _save_output_file(img, filename=filename)
        img_paths.append(path)

    return img_paths


def _parse_aspect_ratio(aspect: str) -> tuple[int, int]:
    """Parse aspect ratio string like '1024×1024' to (width, height)."""
    import re
    m = re.match(r"(\d+)\s*[×x*]\s*(\d+)", aspect)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 1024, 1024


def _get_style_loras(style_selections: list) -> list:
    """Extract LoRA paths from style selections."""
    result = []
    for style in style_selections:
        if isinstance(style, str) and style.startswith("Fooocus"):
            # Fooocus-style presets are applied via prompt, not LoRAs
            pass
    return result


def _wildcards(text: str, seed: int) -> str:
    """Simple wildcard replacement: {random|option1|option2} → random pick."""
    import random
    import re

    def replace_wildcard(match):
        options = match.group(1).split("|")
        rng = random.Random(seed)
        return rng.choice(options)

    return re.sub(r"\{([^}]+)\}", replace_wildcard, text)


def _apply_style(
    prompt: str,
    negative: str,
    styles: list,
) -> tuple[str, str]:
    """Apply style presets to prompt/negative."""
    # Styles are typically prompt templates
    positive_additions = []
    negative_additions = []
    for style in styles:
        if isinstance(style, str):
            # Style names are used as prompt keywords
            positive_additions.append(style)
    if positive_additions:
        prompt = prompt + ", " + ", ".join(positive_additions)
    return prompt, negative


# --- Performance mode defaults ---

_PERFORMANCE_DEFAULTS = {
    "Extreme Speed": {
        "sampler": "dpmpp_sde_gpu",
        "scheduler": "karras",
        "steps": 6,
        "cfg": 1.0,
        "refiner": None,
    },
    "Lightning": {
        "sampler": "euler",
        "scheduler": "sgm_uniform",
        "steps": 4,
        "cfg": 1.0,
        "refiner": None,
    },
    "Hyper-SD": {
        "sampler": "dpmpp_sde_gpu",
        "scheduler": "karras",
        "steps": 8,
        "cfg": 1.0,
        "refiner": None,
    },
    "LCM": {
        "sampler": "lcm",
        "scheduler": "lcm",
        "steps": 5,
        "cfg": 1.0,
        "refiner": None,
    },
}


def _apply_performance_defaults(async_task: AsyncTask) -> None:
    """Apply performance mode defaults (steps, sampler, etc.)."""
    perf = async_task.performance_selection
    defaults = _PERFORMANCE_DEFAULTS.get(perf)
    if defaults:
        if async_task.overwrite_step == -1:
            async_task.overwrite_step = defaults["steps"]
        if async_task.overwrite_switch == -1:
            async_task.overwrite_switch = defaults["steps"]
        async_task.sampler_name = defaults["sampler"]
        async_task.scheduler_name = defaults["scheduler"]
        if defaults["refiner"] is None:
            async_task.refiner_model_name = "None"


def _parse_image_prompts(image_prompts: list) -> dict[str, list]:
    """Parse image_prompts into cn_tasks format.

    Accepts both dict format (from V2 JSON API) and tuple format
    (from req_to_params conversion: (cn_img, cn_stop, cn_weight, cn_type)).
    """
    cn_tasks: dict[str, list] = {"cn_ip": [], "cn_ip_face": [], "cn_canny": [], "cn_cpds": [], "cn_openpose": []}
    for prompt_item in image_prompts:
        img = None
        stop = 0.5
        weight = 1.0
        cn_type = "ImagePrompt"

        if isinstance(prompt_item, dict):
            img = prompt_item.get("cn_img")
            stop = prompt_item.get("cn_stop", 0.5)
            weight = prompt_item.get("cn_weight", 1.0)
            cn_type = prompt_item.get("cn_type", "ImagePrompt")
        elif isinstance(prompt_item, (tuple, list)) and len(prompt_item) >= 4:
            img, stop, weight, cn_type = prompt_item[0], prompt_item[1], prompt_item[2], prompt_item[3]
        else:
            continue

        if img:
            type_map = {
                "ImagePrompt": "cn_ip",
                "FaceSwap": "cn_ip_face",
                "PyraCanny": "cn_canny",
                "CPDS": "cn_cpds",
                "OpenPose": "cn_openpose",
            }
            key = type_map.get(cn_type, "cn_ip")
            cn_tasks[key].append([img, stop, weight])
    return cn_tasks


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

    use_fp16 = True  # SDXL always fp16
    dtype = torch.float16 if use_fp16 else torch.float32

    # Load state dict
    ip_state_dict = torch.load(faceid_adapter_path, map_location="cpu", weights_only=True)
    cross_attention_dim = 2048  # SDXL

    # --- 1. Build image_proj model (projection + perceiver resampler) ---
    # The state dict has: proj.0 (512→1024), perceiver_resampler (Resampler), norm (2048)
    # Build manually since standard IPAdapterModel can't handle this layout

    class FaceIDProj(torch.nn.Module):
        def __init__(self, state_dict):
            super().__init__()
            # Linear projection: 512 → 1024
            self.proj = torch.nn.Sequential(
                torch.nn.Linear(512, 1024),
                torch.nn.GELU(),
                torch.nn.Linear(1024, 8192),
            )
            # Perceiver Resampler
            from extras.resampler import Resampler
            self.perceiver = Resampler(
                dim=2048, depth=4, dim_head=64, heads=20,
                num_queries=4, embedding_dim=1280, output_dim=2048, ff_mult=4,
            )
            self.norm = torch.nn.LayerNorm(2048)

            # Load weights with prefix mapping
            proj_sd = {}
            for k, v in state_dict.items():
                if k.startswith("proj."):
                    proj_sd[k] = v
                elif k.startswith("perceiver_resampler."):
                    proj_sd["perceiver." + k[len("perceiver_resampler."):]] = v
                elif k.startswith("norm."):
                    proj_sd[k] = v

            missing, unexpected = self.load_state_dict(proj_sd, strict=False)
            if missing:
                logger.warning("FaceID proj missing keys: %s", missing[:5])
            logger.info("FaceID proj loaded (proj + perceiver + norm)")

        def forward(self, embeds):
            """embeds: [B, 512] InsightFace embedding → [B, 4, 2048] cross-attention tokens"""
            x = self.proj(embeds)  # [B, 512] → [B, 8192]
            # Reshape to sequence for perceiver: [B, 1, 8192] → but perceiver expects [B, N, D]
            # The Resampler's proj_in expects [B, N, 1280], so we need to adapt
            # Actually the Resampler takes variable-length sequences
            # For single embedding, treat as [B, 1, 8192] and let Resampler handle it
            x = x.unsqueeze(1)  # [B, 1, 8192]
            # Project to perceiver dimension
            x = self.perceiver(x)  # [B, 4, 2048]
            x = self.norm(x)
            return x

    # --- 2. Build LoRA + IP KV layers ---
    class FaceIDIPAdapter(torch.nn.Module):
        """FaceID Plus v2 with LoRA modifications + standard IP-Adapter KV injection."""
        def __init__(self, state_dict, cross_attention_dim=2048):
            super().__init__()
            self.cross_attention_dim = cross_attention_dim

            # Extract unique block indices from ip_adapter keys
            # Keys like "0.to_q_lora.down.weight", "1.to_k_ip.weight"
            block_indices = set()
            for k in state_dict.keys():
                idx = k.split(".")[0]
                if idx.isdigit():
                    block_indices.add(int(idx))
            self.block_indices = sorted(block_indices)
            logger.info("FaceID IP-Adapter: %d blocks", len(self.block_indices))

            # For each block, create to_k_ip and to_v_ip linear layers
            self.to_kvs = torch.nn.ModuleList()
            for idx in self.block_indices:
                # Determine output dimension from state dict
                k_key = f"{idx}.to_k_ip.weight"
                if k_key in state_dict:
                    out_dim = state_dict[k_key].shape[0]
                else:
                    out_dim = 640  # default for SDXL
                to_kv = torch.nn.Linear(cross_attention_dim, out_dim * 2, bias=False)
                # Load weights
                if k_key in state_dict:
                    to_kv.weight.data[:out_dim] = state_dict[k_key]
                v_key = f"{idx}.to_v_ip.weight"
                if v_key in state_dict:
                    to_kv.weight.data[out_dim:] = state_dict[v_key]
                self.to_kvs.append(to_kv)

        def forward(self, cond):
            """cond: [B, 4, 2048] → list of KV tensors for each block"""
            results = []
            for i, to_kv in enumerate(self.to_kvs):
                kv = to_kv(cond.to(to_kv.weight.device, dtype=to_kv.weight.dtype))
                results.append(kv)
            return results

    with use_patched_ops(manual_cast):
        faceid_proj = FaceIDProj(ip_state_dict["image_proj"])
        faceid_proj = faceid_proj.to(offload_device, dtype=dtype)
        faceid_proj.eval()

        faceid_ip = FaceIDIPAdapter(ip_state_dict["ip_adapter"], cross_attention_dim)
        faceid_ip = faceid_ip.to(offload_device, dtype=dtype)
        faceid_ip.eval()

    # --- 3. Load CLIP vision (needed for ip_negative) ---
    try:
        from extras import ip_adapter as ip_adapter_mod
        if ip_adapter_mod.clip_vision is None:
            ip_adapter_mod.load_ip_adapter(clip_vision_path, ip_negative_path, "/dev/null")
        ip_negative = ip_adapter_mod.ip_negative
    except Exception:
        ip_negative = None

    # --- 4. Project the 512-d InsightFace embedding ---
    # faceid_embeds is a list of 512-d embeddings (from SE11 faceid_extractor)
    embeds_np = np.array(faceid_embeds, dtype=np.float32)
    embeds_tensor = torch.from_numpy(embeds_np).to(offload_device, dtype=dtype)

    try:
        ldm_patched.modules.model_management.load_model_gpu(faceid_proj.patcher if hasattr(faceid_proj, 'patcher') else None)
    except Exception:
        pass

    with torch.no_grad():
        projected = faceid_proj(embeds_tensor)  # [B, 4, 2048]
        logger.info("FaceID: projected embedding → %s tokens", list(projected.shape))

    # --- 5. Generate KV pairs ---
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
        # Use zeros as unconditional
        for c in ip_conds:
            ip_unconds.append(torch.zeros_like(c))

    # --- 6. Build tasks for patch_model ---
    # Each task: [(ip_conds, ip_unconds), stop, weight]
    faceid_stop = 0.5  # Apply FaceID for first 50% of steps
    tasks = [[(ip_conds, ip_unconds), faceid_stop, faceid_weight]]
    return tasks


def _apply_ip_adapter(async_task, pipeline):
    """Apply IP-Adapter conditioning to the UNet.

    This wires the parsed cn_tasks into the actual IP-Adapter pipeline:
    1. Downloads IP-Adapter models (clip vision, negative, adapter weights)
    2. Loads models via extras/ip_adapter.py
    3. Preprocesses each reference image through CLIP vision
    4. Patches pipeline.final_unet with IP-Adapter attention patches

    The patched UNet then incorporates visual reference information during
    every attention step, guiding the diffusion toward the reference image's
    composition, pose, and color palette.
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

    # Load models for each adapter type used
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
                # Fallback: use face adapter for FaceID tasks
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

    # Preprocess each reference image
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

    # V2: Process FaceID embeddings if provided
    faceid_embeds = async_task.ip_adapter_faceid_embeds
    if faceid_embeds and adapter_paths.get("faceid"):
        try:
            import torch
            faceid_weight = async_task.ip_adapter_faceid_weight
            logger.info("FaceID: processing embedding (dim=%d) with weight=%.2f",
                        len(faceid_embeds[0]) if faceid_embeds else 0, faceid_weight)

            # Load FaceID Plus v2 adapter (has LoRA + Resampler, not standard IP-Adapter)
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


# --- Core processing functions ---

def _process_prompt(
    async_task: AsyncTask,
    pipeline: Any,
) -> tuple[list, bool, list, int]:
    """Process prompt: refresh models, encode text. Returns (tasks, use_expansion, loras, progress)."""
    import random

    seed = int(async_task.seed) if async_task.seed.isdigit() else random.randint(0, 2**32 - 1)
    async_task.seed = str(seed)

    width, height = _parse_aspect_ratio(async_task.aspect_ratios_selection)

    # Apply performance defaults
    _apply_performance_defaults(async_task)

    # Refresh pipeline
    pipeline.refresh_everything(
        refiner_model_name=async_task.refiner_model_name,
        base_model_name=async_task.base_model_name,
        loras=async_task.loras,
        vae_name=async_task.vae_name,
    )

    # Process each image number
    tasks = []
    for i in range(async_task.image_number):
        current_seed = seed + i if not async_task.disable_seed_increment else seed
        prompt = _wildcards(async_task.prompt, current_seed)
        prompt, negative = _apply_style(prompt, async_task.negative_prompt, async_task.style_selections)
        tasks.append({
            "seed": current_seed,
            "prompt": prompt,
            "negative": negative,
            "width": width,
            "height": height,
        })

    return tasks, False, async_task.loras, 0


def _apply_vary(async_task: AsyncTask, tasks: list) -> tuple[list, dict]:
    """Apply upscale/vary mode. Returns modified tasks and state."""
    if not async_task.uov_input_image:
        return tasks, {}

    method = async_task.uov_method or "subtle_variation"
    denoising_map = {
        "subtle_variation": 0.5,
        "strong_variation": 0.85,
        "upscale_15": 0.5,
        "upscale_2": 0.5,
        "upscale_fast": 0.5,
        "upscale_custom": 0.5,
    }
    denoising = denoising_map.get(method, 0.5)
    return tasks, {"mode": "vary", "method": method, "denoising": denoising}


def _apply_inpaint(async_task: AsyncTask, tasks: list, pipeline: Any = None) -> tuple[list, dict]:
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

    # V2: invert mask if requested (white=keep, black=regenerate → white=regenerate, black=keep)
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
    # use_fill only when full denoise (Fooocus pattern: strength > 0.99)
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
            "negative": async_task.inpaint_negative_prompt,
            "strength": async_task.inpaint_strength,
        }

    try:
        import ldm_patched.modules.model_management

        device = ldm_patched.modules.model_management.get_torch_device()

        # Convert interested_fill (HWC uint8) to tensor [1, C, H, W] float [0,1]
        # Use torch.tensor() to guarantee non-inference tensor (not torch.from_numpy)
        fill_np = worker.interested_fill.astype(np.float32) / 255.0
        fill_tensor = torch.tensor(fill_np, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)

        # Convert interested_mask to tensor [1, 1, H, W] float [0,1]
        mask_np = (worker.interested_mask > 0.5).astype(np.float32) if worker.interested_mask.max() <= 1.0 else worker.interested_mask.astype(np.float32) / 255.0
        mask_tensor = torch.tensor(mask_np, dtype=torch.float32).unsqueeze(0)
        mask_chw = mask_tensor.unsqueeze(1)  # [1, 1, H, W]

        # Apply mask blending (matching encode_vae_inpaint logic):
        # masked region → 0.5 (gray), unmasked region → original pixel values
        blended = fill_tensor * (1 - mask_chw) + 0.5 * mask_chw

        # Move to GPU — ensure tensors are NOT inference tensors
        blended = blended.to(device=device)
        mask_tensor = mask_tensor.to(device=device)

        # Encode blended image to latent via VAE
        # Must run inside @torch.inference_mode() to match the context where the
        # VAE model weights were loaded (refresh_base_model uses @_no_grad → inference_mode)
        latent = None
        with torch.inference_mode():
            latent = vae.encode(blended)  # [1, 4, h, w]

        # Create latent-space mask: upsample mask to latent dimensions, pool by 8
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

        # Set global current_task → activates patched_KSamplerX0Inpaint_forward
        miw.current_task = worker

        inpaint_latent = latent
        inpaint_latent_mask = latent_mask

        logger.warning(
            "Inpaint VAE encoded: latent shape=%s, mask shape=%s",
            list(latent.shape), list(latent_mask.shape),
        )

        # CUDA memory cleanup: release temporary tensors without breaking pipeline
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
                # Store patched model for use in _process_diffusion
                # We don't replace pipeline.final_unet because the pipeline
                # handles model cloning internally. Instead, we store it in state.
                logger.warning("InpaintHead patched into UNet successfully")

                # P0 CRITICAL: Load inpaint patch model as LoRA (Fooocus pattern)
                # This adds fine-tuned inpaint weights to the UNet
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
                        # Load inpaint patch directly into existing UNet via add_patches
                        # This avoids refresh_loras() which recreates unet_with_lora from scratch
                        import ldm_patched.modules.utils as _utils
                        from modules.core import match_lora

                        lora_data = _utils.load_torch_file(inpaint_patch_path, safe_load=False)

                        model_obj = pipeline.model_base
                        unet = model_obj.unet if model_obj else None
                        if unet is not None:
                            # Build key map from current UNet state dict
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
                        # Release inpaint patch from CPU RAM (~1.3GB freed)
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
        # Fall back to text-to-image without inpainting
        miw.current_task = None

    return tasks, {
        "mode": "inpaint",
        "worker": worker,
        "prompt": async_task.inpaint_additional_prompt or "",
        "negative": async_task.inpaint_negative_prompt,
        "strength": async_task.inpaint_strength,
        "inpaint_latent": inpaint_latent,
        "inpaint_latent_mask": inpaint_latent_mask,
    }


def _apply_upscale(async_task: AsyncTask, tasks: list) -> tuple[list, dict]:
    """Apply upscale mode. Returns modified tasks and state."""
    if async_task.uov_method not in ("upscale_15", "upscale_2", "upscale_fast", "upscale_custom"):
        return tasks, {}

    scale_map = {"upscale_15": 1.5, "upscale_2": 2.0, "upscale_fast": 1.0, "upscale_custom": 1.0}
    scale = scale_map.get(async_task.uov_method, 1.5)
    upscale_value = async_task.upscale_value if async_task.uov_method == "upscale_custom" else None

    return tasks, {
        "mode": "upscale",
        "scale": upscale_value or scale,
        "method": async_task.uov_method,
    }


def _apply_freeu(async_task: AsyncTask, pipeline: Any) -> None:
    """Apply FreeU patch if enabled."""
    if not async_task.freeu_enabled:
        return
    try:
        from app.infrastructure.operators import FreeU_V2
        if pipeline.model_base and pipeline.model_base.has_unet:
            FreeU_V2.patch(
                pipeline.model_base.unet.model,
                async_task.freeu_b1,
                async_task.freeu_b2,
                async_task.freeu_s1,
                async_task.freeu_s2,
            )
    except Exception as e:
        logger.warning("Failed to apply FreeU: %s", e)


def _apply_controlnet(
    async_task: AsyncTask,
    pipeline: Any,
    positive_cond: Any,
    negative_cond: Any,
    width: int,
    height: int,
) -> tuple[Any, Any]:
    """Apply ControlNet conditioning (OpenPose) to positive/negative conditioning.

    Loads the OpenPose ControlNet model on demand and applies it for each
    OpenPose control image provided in cn_tasks.
    """
    import base64
    import numpy as np
    from PIL import Image
    from app.infrastructure.core_ops import load_controlnet, apply_controlnet
    from app.services import preprocessors
    from modules.config import path_controlnet
    import os

    cn_openpose = async_task.cn_tasks.get("cn_openpose", [])
    if not cn_openpose:
        return positive_cond, negative_cond

    import cv2
    import torch
    import modules.core as core

    openpose_path = os.path.join(path_controlnet, "controlnet-union-sdxl-1.0.safetensors")
    if not os.path.exists(openpose_path):
        logger.warning("OpenPose ControlNet model not found: %s", openpose_path)
        return positive_cond, negative_cond

    try:
        controlnet = load_controlnet(openpose_path)
    except Exception as e:
        logger.warning("Failed to load OpenPose ControlNet: %s", e)
        return positive_cond, negative_cond

    def _decode_b64(img_b64: str) -> np.ndarray | None:
        try:
            if "," in img_b64:
                img_b64 = img_b64.split(",", 1)[1]
            img_bytes = base64.b64decode(img_b64)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            return np.array(img).astype(np.uint8)
        except Exception as e:
            logger.warning("Failed to decode control image: %s", e)
            return None

    def _decode_bytes(img_bytes: bytes) -> np.ndarray | None:
        try:
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            return np.array(img).astype(np.uint8)
        except Exception as e:
            logger.warning("Failed to decode control image bytes: %s", e)
            return None

    for cn_img_b64, cn_stop, cn_weight in cn_openpose:
        img = None
        if isinstance(cn_img_b64, str):
            img = _decode_b64(cn_img_b64)
        elif isinstance(cn_img_b64, bytes):
            img = _decode_bytes(cn_img_b64)
        elif isinstance(cn_img_b64, np.ndarray):
            img = cn_img_b64
        elif hasattr(cn_img_b64, "convert"):
            img = np.array(cn_img_b64.convert("RGB")).astype(np.uint8)
        else:
            logger.warning("OpenPose control image has unexpected type: %s", type(cn_img_b64).__name__)
            continue

        if img is None:
            continue

        logger.info("OpenPose control image | raw_shape=%s dtype=%s target=%dx%d", img.shape, img.dtype, width, height)

        # Ensure contiguous uint8 HWC array for OpenCV
        img = np.ascontiguousarray(img)
        if img.dtype != np.uint8:
            img = img.astype(np.uint8)

        # Resize to target diffusion size
        img = cv2.resize(img, (width, height), interpolation=cv2.INTER_LANCZOS4)
        img = preprocessors.openpose_identity(img)
        logger.info("OpenPose control image | resized_shape=%s", img.shape)

        # Convert to tensor [B, H, W, C] float — ComfyUI's ControlNetApplyAdvanced
        # internally does image.movedim(-1,1) to obtain [B, C, H, W].
        img_tensor = torch.from_numpy(img.astype(np.float32) / 255.0).unsqueeze(0)

        try:
            positive_cond, negative_cond = apply_controlnet(
                positive_cond, negative_cond,
                controlnet, img_tensor,
                strength=float(cn_weight),
                start_percent=0.0,
                end_percent=float(cn_stop),
            )
            logger.info("Applied OpenPose ControlNet | weight=%.2f stop=%.2f", cn_weight, cn_stop)
        except Exception as e:
            logger.warning("Failed to apply OpenPose ControlNet: %s", e)

    return positive_cond, negative_cond


def _process_diffusion(
    pipeline: Any,
    async_task: AsyncTask,
    task: dict,
    progress_callback: Any | None = None,
    inpaint_state: dict | None = None,
) -> list[Any]:
    """Run the actual diffusion process. Returns list of output images.

    When inpaint_state is provided with an inpaint_latent, uses it instead of
    generating an empty latent. This activates the full inpainting pipeline:
    - patched_KSamplerX0Inpaint_forward mixes latent+noise in unmasked regions
    - InpaintHead features guide the UNet in masked regions
    """
    import numpy as np

    seed = task["seed"]
    width = task["width"]
    height = task["height"]

    # Use inpaint latent if available, otherwise generate empty latent
    if inpaint_state and inpaint_state.get("inpaint_latent") is not None:
        latent_tensor = inpaint_state["inpaint_latent"]
        mask_tensor = inpaint_state.get("inpaint_latent_mask")
        initial_latent = {"samples": latent_tensor}
        if mask_tensor is not None:
            initial_latent["noise_mask"] = mask_tensor
        logger.info("Diffusion using INPAINT latent (shape=%s)", list(latent_tensor.shape))
    else:
        from app.infrastructure.core_ops import generate_empty_latent
        initial_latent = generate_empty_latent(width, height, 1)
        logger.info("Diffusion using EMPTY latent (text-to-image)")

    # CLIP encode — use inpaint_additional_prompt if available
    if async_task.clip_skip:
        pipeline.set_clip_skip(async_task.clip_skip)
    positive_cond = pipeline.clip_encode([task["prompt"]])
    negative_cond = pipeline.clip_encode([task["negative"]])

    # Apply ControlNet conditioning (OpenPose) if present
    positive_cond, negative_cond = _apply_controlnet(
        async_task, pipeline, positive_cond, negative_cond, width, height
    )

    # Calculate steps
    steps = async_task.overwrite_step if async_task.overwrite_step > 0 else 30
    switch = async_task.overwrite_switch if async_task.overwrite_switch > 0 else steps

    # Process diffusion
    denoise = 1.0
    if inpaint_state and inpaint_state.get("strength") is not None:
        denoise = float(inpaint_state["strength"])
        logger.info("Inpaint denoise strength = %.2f", denoise)

    imgs = pipeline.process_diffusion(
        positive_cond=positive_cond,
        negative_cond=negative_cond,
        steps=steps,
        switch=switch,
        width=width,
        height=height,
        image_seed=seed,
        callback=progress_callback,
        sampler_name=async_task.sampler_name,
        scheduler_name=async_task.scheduler_name,
        latent=initial_latent,
        denoise=denoise,
    )

    return imgs if imgs else []


def process_generate(async_job: QueueTask) -> None:
    """Main generation function. Processes one task end-to-end.

    Decorated with @torch.no_grad() + @torch.inference_mode() in the caller.
    """
    inpaint_worker_ref = None
    try:
        # Build async task from request params
        async_task = _build_async_task(async_job.req_param)

        # Import pipeline
        from app.services.pipeline import get_pipeline
        pipeline = get_pipeline()

        # Create outputs collector
        outputs = TaskOutputs(async_job)

        # Start progress
        async_job.set_progress(0, "Starting...")
        async_job.task_status = "Processing"

        # Step 1: Parse image prompts
        if async_task.image_prompts:
            cn_tasks = _parse_image_prompts(async_task.image_prompts)
            async_task.cn_tasks.update(cn_tasks)

        # Step 2: Process prompt (refresh models, encode text)
        tasks, use_expansion, loras, progress = _process_prompt(async_task, pipeline)
        async_job.set_progress(10, "Prompt processed")

        # Step 3: Apply image input modes
        vary_state = {}
        inpaint_state = {}
        upscale_state = {}

        if async_task.uov_method:
            if async_task.uov_method in ("subtle_variation", "strong_variation"):
                tasks, vary_state = _apply_vary(async_task, tasks)
            else:
                tasks, upscale_state = _apply_upscale(async_task, tasks)

        if async_task.inpaint_input_image:
            tasks, inpaint_state = _apply_inpaint(async_task, tasks, pipeline)

        # Step 3c: Apply IP-Adapter (visual reference from original image)
        # Must run AFTER inpaint (patches accumulate via model.clone())
        _apply_ip_adapter(async_task, pipeline)

        # Step 3b: InpaintWorker reference for post_process (crop paste)
        inpaint_worker_ref = None
        if inpaint_state.get("mode") == "inpaint":
            inpaint_worker_ref = inpaint_state["worker"]
            logger.info("InpaintWorker: crop=%dx%d, will post_process after diffusion",
                        inpaint_worker_ref.interested_image.shape[1],
                        inpaint_worker_ref.interested_image.shape[0])

        # Step 4: Apply FreeU
        _apply_freeu(async_task, pipeline)

        # Step 5: Run diffusion for each task
        all_images = []
        total_tasks = len(tasks)

        for idx, task in enumerate(tasks):
            # Check for interrupt
            try:
                from app.services.model_manager import get_model_manager
                if get_model_manager().processing_interrupted():
                    async_job.set_result([], True, "Interrupted by user")
                    return
            except Exception:
                pass

            progress = 20 + int(70 * idx / max(total_tasks, 1))
            async_job.set_progress(progress, f"Generating {idx + 1}/{total_tasks}")

            def progress_callback(step, x0=None, x=None, total=None, preview=None):
                total_steps = total if total is not None else 30
                step_progress = 20 + int(70 * (idx + step / max(total_steps, 1)) / max(total_tasks, 1))
                async_job.set_progress(step_progress, f"Step {step}/{total_steps}")
                if x0 is not None:
                    try:
                        import base64
                        import numpy as np
                        from PIL import Image
                        if isinstance(x0, np.ndarray):
                            img = Image.fromarray(x0)
                            buf = io.BytesIO()
                            img.save(buf, format="PNG")
                            b64 = base64.b64encode(buf.getvalue()).decode()
                            async_job.set_step_preview(f"data:image/png;base64,{b64}")
                    except Exception:
                        pass

            imgs = _process_diffusion(pipeline, async_task, task, progress_callback, inpaint_state=inpaint_state)

            # Post-process inpaint: paste crop back into original image
            if inpaint_worker_ref is not None and imgs:
                postprocessed = []
                for img in imgs:
                    try:
                        result = inpaint_worker_ref.post_process(img)
                        postprocessed.append(result)
                    except Exception as e:
                        logger.warning("InpaintWorker post_process failed: %s", e)
                        postprocessed.append(img)
                imgs = postprocessed

            all_images.extend(imgs)

        # Step 6: Save results
        async_job.set_progress(95, "Saving results...")
        img_paths = _save_and_log(
            async_task, all_images, loras, use_expansion,
            tasks[0]["width"] if tasks else 1024,
            tasks[0]["height"] if tasks else 1024,
        )

        # Step 7: Build results
        results = []
        for i, path in enumerate(img_paths):
            seed = tasks[i]["seed"] if i < len(tasks) else 0
            if async_task.require_base64:
                try:
                    with open(path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    results.append(ImageGenerationResult(
                        im=None,
                        seed=str(seed),
                        finish_reason=GenerationFinishReason.SUCCESS,
                    ))
                    results[-1].im = f"data:image/png;base64,{b64}"
                except Exception:
                    results.append(ImageGenerationResult(
                        im=path, seed=str(seed),
                        finish_reason=GenerationFinishReason.SUCCESS,
                    ))
            else:
                results.append(ImageGenerationResult(
                    im=path, seed=str(seed),
                    finish_reason=GenerationFinishReason.SUCCESS,
                ))

        async_job.set_result(results, False)
        async_job.set_progress(100, "Finished")

        # Prepare encoder for next task
        pipeline.prepare_text_encoder(async_call=True)

        # Post-generation memory cleanup — helps mimalloc return freed pages to OS
        import gc
        pipeline.clear_caches()
        gc.collect()

    except Exception as e:
        logger.exception("Generation failed: %s", e)
        async_job.set_result([], True, str(e))
    finally:
        # Clean up InpaintWorker reference and global state
        inpaint_worker_ref = None
        try:
            import modules.inpaint_worker
            modules.inpaint_worker.current_task = None
        except (ImportError, AttributeError):
            pass

        # Clear pipeline caches (ControlNet, CLIP encode)
        try:
            _p = get_pipeline()
            _p.loaded_controlnets.clear()
            _p._clip_cond_cache.clear()
        except Exception:
            pass

        # Unload SE8 model_manager (CLIP, Expansion, IP-Adapter, etc.)
        try:
            from app.services.model_manager import get_model_manager
            get_model_manager().unload_all()
        except Exception:
            pass

        # Offload GPU models to free VRAM after job completion (ComfyUI UNet/VAE/ControlNet)
        try:
            import ldm_patched.modules.model_management as model_management
            model_management.unload_all_models()
            model_management.soft_empty_cache()
        except Exception:
            pass
        import gc
        gc.collect()
        # Force glibc to release freed memory pages back to OS
        try:
            import ctypes
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:
            pass
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except Exception:
            pass
        if worker_queue:
            worker_queue.finish_task(async_job.job_id)


def task_schedule_loop() -> None:
    """Main worker loop. Processes tasks one at a time from the queue.

    When idle for AUTO_RESTART_IDLE_SECONDS, restarts the process via os.execv
    to reclaim all PyTorch mmap'd memory. Controlled by SE8_AUTO_RESTART_IDLE env var.
    """
    logger.info("Worker task loop started")

    auto_restart_idle = int(os.environ.get("SE8_AUTO_RESTART_IDLE", "0"))
    last_task_finish_time = time.monotonic()
    had_tasks = False

    while True:
        if worker_queue is None or not worker_queue.queue:
            if had_tasks and auto_restart_idle > 0:
                idle_seconds = time.monotonic() - last_task_finish_time
                if idle_seconds >= auto_restart_idle:
                    logger.info("Auto-restart: idle for %.0fs (threshold=%ds), restarting process", idle_seconds, auto_restart_idle)
                    import sys
                    os.execv(sys.executable, ["python3.11", "-m", "uvicorn", "app.main:app",
                                               "--host", "0.0.0.0", "--port", "8008"])
            time.sleep(0.05)
            continue

        current_task = worker_queue.queue[0]

        if current_task.start_mills == 0:
            try:
                worker_queue.start_task(current_task.job_id)
                process_generate(current_task)
                had_tasks = True
                last_task_finish_time = time.monotonic()
            except Exception as e:
                logger.exception("Task failed: %s", e)
                current_task.set_result([], True, str(e))
                worker_queue.finish_task(current_task.job_id)
                had_tasks = True
                last_task_finish_time = time.monotonic()
        else:
            time.sleep(0.05)


def blocking_get_task_result(job_id: str) -> list[ImageGenerationResult] | None:
    """Poll for task result (synchronous). Used by sync API endpoints."""
    if worker_queue is None:
        return None

    while True:
        task = worker_queue.get_task(job_id, include_history=True)
        if task is None:
            return None
        if task.is_finished:
            return task.task_result
        time.sleep(0.05)
