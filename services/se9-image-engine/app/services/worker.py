"""GPU worker for SE9 Image Engine.

Single-threaded GPU worker that processes image generation tasks.
Clean-room rewrite of FOOOCUS fooocusapi/worker.py.

Architecture:
- task_schedule_loop() runs in a thread, processes one task at a time
- process_generate() is the core function, decorated with @torch.no_grad()
- Each task goes through: image_input → prompt → vary/upscale/inpaint → diffusion → save
"""

from __future__ import annotations

import base64
import io
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

logger = logging.getLogger(__name__)

# Module-level state
worker_queue: Optional[TaskQueue] = None
_last_model_name: Optional[str] = None


def process_stop() -> None:
    """Interrupt current processing."""
    try:
        from app.services.model_manager import get_model_manager
        get_model_manager().interrupt_current_processing()
    except Exception as e:
        logger.warning("Failed to interrupt processing: %s", e)


def _detect_task_type(req: Dict[str, Any]) -> TaskType:
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


def _build_async_task(req: Dict[str, Any]) -> AsyncTask:
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
        save_metadata_to_images=adv.get("save_metadata_to_images", False),
        metadata_scheme=adv.get("metadata_scheme", "fooocus"),
        save_final_enhanced_image_only=req.get("save_final_enhanced_image_only", True),
        require_base64=req.get("require_base64", False),
        webhook_url=req.get("webhook_url"),
        outpaint_distance_left=req.get("outpaint_distance_left", 0),
        outpaint_distance_top=req.get("outpaint_distance_top", 0),
        outpaint_distance_right=req.get("outpaint_distance_right", 0),
        outpaint_distance_bottom=req.get("outpaint_distance_bottom", 0),
    )


def _save_output_file(
    img,
    output_dir: str = "",
    subfolder: str = "",
    filename: Optional[str] = None,
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
) -> List[str]:
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


def _parse_aspect_ratio(aspect: str) -> Tuple[int, int]:
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
            # Fooocus styles are applied via prompt, not LoRAs
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
) -> Tuple[str, str]:
    """Apply Fooocus styles to prompt/negative."""
    # Styles are typically prompt templates
    positive_additions = []
    negative_additions = []
    for style in styles:
        if isinstance(style, str):
            # Fooocus uses style names as prompt keywords
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


def _parse_image_prompts(image_prompts: list) -> Dict[str, List]:
    """Parse V2 image_prompts into cn_tasks format."""
    cn_tasks: Dict[str, List] = {"cn_ip": [], "cn_ip_face": [], "cn_canny": [], "cn_cpds": []}
    for prompt_item in image_prompts:
        if not isinstance(prompt_item, dict):
            continue
        img = prompt_item.get("cn_img")
        stop = prompt_item.get("cn_stop", 0.5)
        weight = prompt_item.get("cn_weight", 1.0)
        cn_type = prompt_item.get("cn_type", "ImagePrompt")
        if img:
            type_map = {
                "ImagePrompt": "cn_ip",
                "FaceSwap": "cn_ip_face",
                "PyraCanny": "cn_canny",
                "CPDS": "cn_cpds",
            }
            key = type_map.get(cn_type, "cn_ip")
            cn_tasks[key].append([img, stop, weight])
    return cn_tasks


# --- Core processing functions ---

def _process_prompt(
    async_task: AsyncTask,
    pipeline: Any,
) -> Tuple[list, bool, list, int]:
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


def _apply_vary(async_task: AsyncTask, tasks: list) -> Tuple[list, dict]:
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


def _apply_inpaint(async_task: AsyncTask, tasks: list) -> Tuple[list, dict]:
    """Apply inpaint mode. Returns modified tasks and state."""
    if not async_task.inpaint_input_image:
        return tasks, {}

    return tasks, {
        "mode": "inpaint",
        "prompt": async_task.inpaint_additional_prompt or "",
        "negative": async_task.inpaint_negative_prompt,
        "strength": async_task.inpaint_strength,
    }


def _apply_upscale(async_task: AsyncTask, tasks: list) -> Tuple[list, dict]:
    """Apply upscale mode. Returns modified tasks and state."""
    if async_task.uov_method not in ("upscale_15", "upscale_2", "upscale_fast", "upscale_custom"):
        return tasks, {}

    scale_map = {"upscale_15": 1.5, "upscale_2": 2.0, "upscale_fast": 1.0, "upscale_custom": 1.0}
    scale = scale_map.get(async_task.uov_method, 1.5)
    upscale_value = async_task.upscale_value if async_task.upscale_method == "upscale_custom" else None

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


def _process_diffusion(
    pipeline: Any,
    async_task: AsyncTask,
    task: dict,
    progress_callback: Optional[Any] = None,
) -> List[Any]:
    """Run the actual diffusion process. Returns list of output images."""
    import numpy as np

    seed = task["seed"]
    width = task["width"]
    height = task["height"]

    # Generate empty latent
    from app.infrastructure.core_ops import generate_empty_latent
    initial_latent = generate_empty_latent(width, height, 1)

    # CLIP encode
    positive_cond, negative_cond = pipeline.clip_encode(
        task["prompt"],
        task["negative"],
        clip_skip=async_task.clip_skip,
    )

    # Calculate steps
    steps = async_task.overwrite_step if async_task.overwrite_step > 0 else 30
    switch = async_task.overwrite_switch if async_task.overwrite_switch > 0 else steps

    # Process diffusion
    imgs = pipeline.process_diffusion(
        seed=seed,
        positive_cond=positive_cond,
        negative_cond=negative_cond,
        initial_latent=initial_latent,
        width=width,
        height=height,
        steps=steps,
        switch=switch,
        callback=progress_callback,
    )

    return imgs if imgs else []


def process_generate(async_job: QueueTask) -> None:
    """Main generation function. Processes one task end-to-end.

    Decorated with @torch.no_grad() + @torch.inference_mode() in the caller.
    """
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
            tasks, inpaint_state = _apply_inpaint(async_task, tasks)

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

            def progress_callback(step: int, total: int, preview=None):
                step_progress = 20 + int(70 * (idx + step / max(total, 1)) / max(total_tasks, 1))
                async_job.set_progress(step_progress, f"Step {step}/{total}")
                if preview is not None:
                    try:
                        import base64
                        import numpy as np
                        from PIL import Image
                        if isinstance(preview, np.ndarray):
                            img = Image.fromarray(preview)
                            buf = io.BytesIO()
                            img.save(buf, format="PNG")
                            b64 = base64.b64encode(buf.getvalue()).decode()
                            async_job.set_step_preview(f"data:image/png;base64,{b64}")
                    except Exception:
                        pass

            imgs = _process_diffusion(pipeline, async_task, task, progress_callback)
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

    except Exception as e:
        logger.exception("Generation failed: %s", e)
        async_job.set_result([], True, str(e))
    finally:
        if worker_queue:
            worker_queue.finish_task(async_job.job_id)


def task_schedule_loop() -> None:
    """Main worker loop. Processes tasks one at a time from the queue."""
    logger.info("Worker task loop started")

    while True:
        if worker_queue is None or not worker_queue.queue:
            time.sleep(0.05)
            continue

        current_task = worker_queue.queue[0]

        if current_task.start_mills == 0:
            try:
                worker_queue.start_task(current_task.job_id)
                process_generate(current_task)
            except Exception as e:
                logger.exception("Task failed: %s", e)
                current_task.set_result([], True, str(e))
                worker_queue.finish_task(current_task.job_id)
        else:
            time.sleep(0.05)


def blocking_get_task_result(job_id: str) -> Optional[List[ImageGenerationResult]]:
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
