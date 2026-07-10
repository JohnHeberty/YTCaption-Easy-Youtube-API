"""GPU worker for SE8 Image Engine.

Single-threaded GPU worker that processes image generation tasks.

Architecture:
- task_schedule_loop() runs in a thread, processes one task at a time
- process_generate() is the core function, decorated with @torch.no_grad()
- Each task goes through: image_input → prompt → vary/upscale/inpaint → diffusion → save

Modules extracted:
- task_builder.py: AsyncTask construction, parsing, performance defaults
- prompt_processor.py: wildcard replacement, style application, prompt processing
- inpaint_processor.py: full Fooocus inpaint flow
- image_processors.py: vary, upscale, FreeU, ControlNet
- output_saver.py: image saving and result building
"""
from __future__ import annotations
from common.log_utils import get_logger

import base64
import io
import os
import time
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
from app.services.ip_adapter_worker import _apply_ip_adapter, _load_faceid_adapter
from app.services.task_builder import (
    build_async_task,
    detect_task_type,
    parse_image_prompts,
)
from app.services.prompt_processor import process_prompt
from app.services.inpaint_processor import apply_inpaint
from app.services.image_processors import apply_vary, apply_upscale, apply_freeu, apply_controlnet
from app.services.output_saver import save_and_log
from app.services.task_type_registry import create_default_registry

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


# ─── Core orchestrator ────────────────────────────────────────────────────────

def _process_diffusion(
    pipeline: Any,
    async_task: AsyncTask,
    task: dict,
    progress_callback: Any | None = None,
    inpaint_state: dict | None = None,
) -> list[Any]:
    """Run the actual diffusion process. Returns list of output images."""
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

    # CLIP encode
    if async_task.clip_skip:
        pipeline.set_clip_skip(async_task.clip_skip)
    positive_cond = pipeline.clip_encode([task["prompt"]])
    negative_cond = pipeline.clip_encode([task["negative"]])

    # Apply ControlNet conditioning (OpenPose) if present
    positive_cond, negative_cond = apply_controlnet(
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
        async_task = build_async_task(async_job.req_param)

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
            cn_tasks = parse_image_prompts(async_task.image_prompts)
            async_task.cn_tasks.update(cn_tasks)

        # Step 2: Process prompt (refresh models, encode text)
        tasks, use_expansion, loras, progress = process_prompt(async_task, pipeline)
        async_job.set_progress(10, "Prompt processed")

        # Step 3: Apply image input modes
        vary_state = {}
        inpaint_state = {}
        upscale_state = {}

        if async_task.uov_method:
            if async_task.uov_method in ("subtle_variation", "strong_variation"):
                tasks, vary_state = apply_vary(async_task, tasks)
            else:
                tasks, upscale_state = apply_upscale(async_task, tasks)

        if async_task.inpaint_input_image:
            tasks, inpaint_state = apply_inpaint(async_task, tasks, pipeline)

        # Step 3c: Apply IP-Adapter (visual reference from original image)
        _apply_ip_adapter(async_task, pipeline)

        # Step 3b: InpaintWorker reference for post_process
        inpaint_worker_ref = None
        if inpaint_state.get("mode") == "inpaint":
            inpaint_worker_ref = inpaint_state["worker"]
            logger.info("InpaintWorker: crop=%dx%d, will post_process after diffusion",
                        inpaint_worker_ref.interested_image.shape[1],
                        inpaint_worker_ref.interested_image.shape[0])

        # Step 4: Apply FreeU
        apply_freeu(async_task, pipeline)

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
        img_paths = save_and_log(
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

        # Post-generation memory cleanup
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

        # Clear pipeline caches
        try:
            _p = get_pipeline()
            _p.loaded_controlnets.clear()
            _p._clip_cond_cache.clear()
        except Exception:
            pass

        # Unload SE8 model_manager
        try:
            from app.services.model_manager import get_model_manager
            get_model_manager().unload_all()
        except Exception:
            pass

        # Offload GPU models to free VRAM
        try:
            import ldm_patched.modules.model_management as model_management
            model_management.unload_all_models()
            model_management.soft_empty_cache()
        except Exception:
            pass
        import gc
        gc.collect()
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
    to reclaim all PyTorch mmap'd memory.
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
