"""API utilities for SE8 Image Engine.

Provides call_worker, req_to_params, generate_async_output, and response helpers.
"""

from __future__ import annotations
from common.log_utils import get_logger

import base64
import io
import os
import random
from pathlib import Path
from typing import Any

from fastapi import Response

from app.core.config import get_settings
from app.domain.models import (
    AdvancedParams,
    CommonRequest,
    EnhanceCtrlNets,
    ImageEnhanceRequest,
    ImageEnhanceRequestJson,
    ImagePromptJson,
    ImgInpaintOrOutpaintRequest,
    ImgInpaintOrOutpaintRequestJson,
    ImgPromptRequest,
    ImgPromptRequestJson,
    ImgUpscaleOrVaryRequest,
    ImgUpscaleOrVaryRequestJson,
    Text2ImgRequestWithPrompt,
)
from app.domain.task_models import (
    AsyncTask,
    GenerationFinishReason,
    ImageGenerationResult,
    QueueTask,
    TaskOutputs,
    TaskType,
)
import app.services.worker as _worker_mod

logger = get_logger(__name__)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def refresh_seed(seed_value: Any) -> int:
    """Refresh and validate seed number."""
    from app.core.constants import MAX_SEED, MIN_SEED

    RANDOM_SEED = random.randint(MIN_SEED, MAX_SEED)
    try:
        seed = int(seed_value)
    except (ValueError, TypeError):
        return RANDOM_SEED
    if seed < MIN_SEED or seed > MAX_SEED or seed_value == -1:
        return RANDOM_SEED
    return seed


def get_task_type(req: CommonRequest) -> TaskType:
    """Detect task type from request model."""
    if isinstance(req, (ImgUpscaleOrVaryRequest, ImgUpscaleOrVaryRequestJson)):
        return TaskType.IMG_UPSCALE_VARY
    if isinstance(req, (ImgPromptRequest, ImgPromptRequestJson)):
        return TaskType.IMG_PROMPT
    if isinstance(req, (ImgInpaintOrOutpaintRequest, ImgInpaintOrOutpaintRequestJson)):
        return TaskType.IMG_INPAINT_OUTPAINT
    if isinstance(req, (ImageEnhanceRequest, ImageEnhanceRequestJson)):
        return TaskType.IMG_ENHANCE
    return TaskType.TEXT_TO_IMAGE


def req_to_params(req: CommonRequest) -> dict[str, Any]:
    """Convert a request model to a dict of AsyncTask parameters."""
    settings = get_settings()
    prompt = req.prompt
    negative_prompt = req.negative_prompt
    style_selections = list(req.style_selections)
    performance_selection = req.performance_selection
    aspect_ratios_selection = req.aspect_ratios_selection
    image_number = req.image_number
    image_seed = refresh_seed(req.image_seed)
    sharpness = req.sharpness
    guidance_scale = req.guidance_scale
    base_model_name = req.base_model_name
    refiner_model_name = req.refiner_model_name
    refiner_switch = req.refiner_switch
    loras = [(l.model_name, l.weight) for l in req.loras if l.enabled]

    uov_input_image = None
    uov_method = "Disabled"
    upscale_value = None
    if isinstance(req, (ImgUpscaleOrVaryRequest, ImgUpscaleOrVaryRequestJson)):
        uov_method = req.uov_method
        upscale_value = req.upscale_value
        if req.input_image:
            uov_input_image = _decode_image(req.input_image)

    outpaint_selections = []
    outpaint_distance_left = 0
    outpaint_distance_right = 0
    outpaint_distance_top = 0
    outpaint_distance_bottom = 0
    inpaint_input_image = {"image": None, "mask": None}
    inpaint_additional_prompt = None

    if isinstance(req, (ImgInpaintOrOutpaintRequest, ImgInpaintOrOutpaintRequestJson)):
        outpaint_selections = list(req.outpaint_selections)
        outpaint_distance_left = req.outpaint_distance_left or 0
        outpaint_distance_right = req.outpaint_distance_right or 0
        outpaint_distance_top = req.outpaint_distance_top or 0
        outpaint_distance_bottom = req.outpaint_distance_bottom or 0
        inpaint_additional_prompt = req.inpaint_additional_prompt

        if req.input_image:
            img = _decode_image(req.input_image)
            mask = None
            if req.input_mask:
                mask = _decode_image(req.input_mask)
            inpaint_input_image = {"image": img, "mask": mask}

    image_prompts = []
    if isinstance(
        req,
        (
            ImgInpaintOrOutpaintRequest,
            ImgInpaintOrOutpaintRequestJson,
            ImgPromptRequest,
            ImgPromptRequestJson,
            ImgUpscaleOrVaryRequestJson,
            Text2ImgRequestWithPrompt,
        ),
    ):
        for ip in req.image_prompts:
            cn_img = None
            if ip.cn_img:
                cn_img = _decode_image(ip.cn_img)
            image_prompts.append(
                (
                    cn_img,
                    ip.cn_stop or 0.5,
                    ip.cn_weight or 0.6,
                    ip.cn_type,
                )
            )
    while len(image_prompts) < 4:
        image_prompts.append((None, 0.5, 0.6, "ImagePrompt"))

    enhance_checkbox = False
    enhance_input_image = None
    enhance_uov_method = "Disabled"
    enhance_uov_processing_order = "Before First Enhancement"
    enhance_uov_prompt_type = "Original Prompts"
    enhance_ctrlnets = [EnhanceCtrlNets() for _ in range(3)]

    if isinstance(req, (ImageEnhanceRequest, ImageEnhanceRequestJson)):
        enhance_checkbox = True
        if req.enhance_input_image:
            enhance_input_image = _decode_image(req.enhance_input_image)
        enhance_uov_method = req.enhance_uov_method
        enhance_uov_processing_order = req.enhance_uov_processing_order
        enhance_uov_prompt_type = req.enhance_uov_prompt_type
        if req.enhance_ctrlnets:
            enhance_ctrlnets = req.enhance_ctrlnets

    advanced_params = req.advanced_params or AdvancedParams()

    return {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "style_selections": style_selections,
        "performance_selection": performance_selection,
        "aspect_ratios_selection": aspect_ratios_selection,
        "image_number": image_number,
        "image_seed": image_seed,
        "sharpness": sharpness,
        "guidance_scale": guidance_scale,
        "base_model_name": base_model_name,
        "refiner_model_name": refiner_model_name,
        "refiner_switch": refiner_switch,
        "loras": loras,
        "uov_input_image": uov_input_image,
        "uov_method": uov_method,
        "upscale_value": upscale_value,
        "outpaint_selections": outpaint_selections,
        "outpaint_distance_left": outpaint_distance_left,
        "outpaint_distance_right": outpaint_distance_right,
        "outpaint_distance_top": outpaint_distance_top,
        "outpaint_distance_bottom": outpaint_distance_bottom,
        "inpaint_input_image": inpaint_input_image,
        "inpaint_additional_prompt": inpaint_additional_prompt,
        "enhance_input_image": enhance_input_image,
        "enhance_checkbox": enhance_checkbox,
        "enhance_uov_method": enhance_uov_method,
        "enhance_uov_processing_order": enhance_uov_processing_order,
        "enhance_uov_prompt_type": enhance_uov_prompt_type,
        "enhance_ctrlnets": enhance_ctrlnets,
        "image_prompts": image_prompts,
        "advanced_params": advanced_params,
        "read_wildcards_in_order": req.read_wildcards_in_order,
        "save_meta": req.save_meta,
        "meta_scheme": req.meta_scheme,
        "save_name": req.save_name,
        "save_extension": req.save_extension,
        "require_base64": req.require_base64,
        "async_process": req.async_process,
        "webhook_url": req.webhook_url,
    }


def _decode_image(data: str) -> Any:
    """Decode base64 or URL image to numpy array.

    Returns numpy array for base64 images, or the original string for URLs.
    """
    if not data:
        return None
    if data.startswith(("http://", "https://")):
        return data
    try:
        if "," in data:
            data = data.split(",", 1)[1]
        img_bytes = base64.b64decode(data)
        return img_bytes
    except Exception:
        return data


def call_worker(
    req: CommonRequest, accept: str | None = None
) -> Response | dict[str, Any] | list[dict[str, Any]]:
    """Enqueue a generation task and return results (sync or async)."""
    streaming_output = False
    if accept and "image/png" in accept:
        streaming_output = True
        req.image_number = 1

    task_type = get_task_type(req)
    params = req_to_params(req)
    async_task = _worker_mod.worker_queue.add_task(task_type, params, req.webhook_url)

    if async_task is None:
        failure_results = [
            ImageGenerationResult(
                im=None,
                seed="",
                finish_reason=GenerationFinishReason.queue_is_full,
            )
        ]
        if streaming_output:
            return _generate_streaming_output(failure_results)
        if req.async_process:
            return {
                "job_id": "",
                "job_type": task_type.value,
                "job_stage": "ERROR",
                "job_progress": 0,
                "job_status": None,
                "job_step_preview": None,
                "job_result": [
                    {
                        "base64": None,
                        "url": None,
                        "seed": "",
                        "finish_reason": "QUEUE_IS_FULL",
                    }
                ],
            }
        return _generate_image_result_output(failure_results, False)

    if req.async_process:
        return generate_async_output(async_task)

    results = _worker_mod.blocking_get_task_result(async_task.job_id)

    if streaming_output:
        return _generate_streaming_output(results)
    return _generate_image_result_output(results, req.require_base64)


def generate_async_output(
    task: QueueTask, require_step_preview: bool = False
) -> dict[str, Any]:
    """Generate async job response."""
    job_stage = "RUNNING"
    job_result = None

    if task.start_mills == 0:
        job_stage = "WAITING"

    if task.is_finished:
        if task.finish_with_error:
            job_stage = "ERROR"
        elif task.task_result is not None:
            job_stage = "SUCCESS"
            job_result = _generate_image_result_output(
                task.task_result, task.req_param.get("require_base64", False)
            )

    return {
        "job_id": task.job_id,
        "job_type": task.task_type.value,
        "job_stage": job_stage,
        "job_progress": task.finish_progress,
        "job_status": task.task_status,
        "job_step_preview": task.task_step_preview if require_step_preview else None,
        "job_result": job_result,
    }


def _generate_streaming_output(results: list[ImageGenerationResult]) -> Response:
    """Generate streaming image bytes response."""
    if not results:
        return Response(status_code=500)
    result = results[0]
    if result.finish_reason == GenerationFinishReason.queue_is_full:
        return Response(status_code=409, content=result.finish_reason.value)
    if result.finish_reason == GenerationFinishReason.user_cancel:
        return Response(status_code=400, content=result.finish_reason.value)
    if result.finish_reason == GenerationFinishReason.error:
        return Response(status_code=500, content=result.finish_reason.value)

    img_bytes = _output_file_to_bytes(result.im)
    return Response(img_bytes, media_type="image/png")


def _generate_image_result_output(
    results: list[ImageGenerationResult], require_base64: bool
) -> list[dict[str, Any]]:
    """Convert ImageGenerationResult list to API response format."""
    settings = get_settings()
    output = []
    output_dir = settings.output_dir
    for item in results:
        url = None
        if item.im:
            rel = os.path.relpath(item.im, output_dir)
            url = f"/files/{rel}"
        b64 = None
        if require_base64 and item.im:
            b64 = _output_file_to_base64(item.im)
        output.append(
            {
                "base64": b64,
                "url": url,
                "seed": str(item.seed),
                "finish_reason": item.finish_reason.value,
            }
        )
    return output


def _output_file_to_base64(filepath: str) -> str | None:
    """Read output file and return base64 string."""
    if not filepath:
        return None
    settings = get_settings()
    full_path = os.path.join(settings.output_dir, filepath)
    try:
        with open(full_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def _output_file_to_bytes(filepath: str) -> bytes | None:
    """Read output file and return raw bytes."""
    if not filepath:
        return None
    settings = get_settings()
    full_path = os.path.join(settings.output_dir, filepath)
    try:
        with open(full_path, "rb") as f:
            return f.read()
    except Exception:
        return None
