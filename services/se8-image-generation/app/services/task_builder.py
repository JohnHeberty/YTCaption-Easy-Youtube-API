"""Task construction and parsing — pure data mapping, no GPU, no I/O.

Extracted from worker.py to enable isolated unit testing.
"""
from __future__ import annotations

import re
from typing import Any

from app.domain.task_models import AsyncTask, TaskType
from app.services.task_type_registry import TaskTypeRegistry, create_default_registry

# ─── Performance mode defaults ────────────────────────────────────────────────

PERFORMANCE_DEFAULTS: dict[str, dict[str, Any]] = {
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

# ─── Task type registry ───────────────────────────────────────────────────────

_task_type_registry: TaskTypeRegistry = create_default_registry()


def detect_task_type(req: dict[str, Any]) -> TaskType:
    """Detect task type from request parameters."""
    return _task_type_registry.detect(req)


# ─── AsyncTask construction ───────────────────────────────────────────────────

def build_async_task(req: dict[str, Any]) -> AsyncTask:
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
        output_format=req.get("save_extension", "png"),
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
        save_metadata_to_images=req.get("save_meta", False),
        metadata_scheme=req.get("meta_scheme", "fooocus"),
        save_final_enhanced_image_only=req.get("save_final_enhanced_image_only", True),
        require_base64=req.get("require_base64", False),
        webhook_url=req.get("webhook_url"),
        outpaint_distance_left=req.get("outpaint_distance_left", 0),
        outpaint_distance_top=req.get("outpaint_distance_top", 0),
        outpaint_distance_right=req.get("outpaint_distance_right", 0),
        outpaint_distance_bottom=req.get("outpaint_distance_bottom", 0),
        invert_mask_checkbox=adv.get("invert_mask_checkbox", False),
        ip_adapter_faceid_embeds=req.get("ip_adapter_faceid_embeds"),
        ip_adapter_faceid_weight=req.get("ip_adapter_faceid_weight", 0.8),
    )


# ─── Parsing helpers ──────────────────────────────────────────────────────────

def parse_aspect_ratio(aspect: str) -> tuple[int, int]:
    """Parse aspect ratio string like '1024×1024' to (width, height)."""
    m = re.match(r"(\d+)\s*[×x*]\s*(\d+)", aspect)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 1024, 1024


def get_style_loras(style_selections: list) -> list:
    """Extract LoRA paths from style selections."""
    result = []
    for style in style_selections:
        if isinstance(style, str) and style.startswith("Fooocus"):
            # Fooocus-style presets are applied via prompt, not LoRAs
            pass
    return result


def parse_image_prompts(image_prompts: list) -> dict[str, list]:
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


def apply_performance_defaults(async_task: AsyncTask) -> None:
    """Apply performance mode defaults (steps, sampler, etc.)."""
    perf = async_task.performance_selection
    defaults = PERFORMANCE_DEFAULTS.get(perf)
    if defaults:
        if async_task.overwrite_step == -1:
            async_task.overwrite_step = defaults["steps"]
        if async_task.overwrite_switch == -1:
            async_task.overwrite_switch = defaults["steps"]
        async_task.sampler_name = defaults["sampler"]
        async_task.scheduler_name = defaults["scheduler"]
        if defaults["refiner"] is None:
            async_task.refiner_model_name = "None"
