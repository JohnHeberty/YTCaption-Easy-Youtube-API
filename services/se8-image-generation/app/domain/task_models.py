"""Task models for SE8 Image Engine.

Domain models for generation task lifecycle:
TaskType, AsyncTask, QueueTask, ImageGenerationResult.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskType(str, Enum):
    TEXT_TO_IMAGE = "Text to Image"
    IMG_UPSCALE_VARY = "Image Upscale or Variation"
    IMG_INPAINT_OUTPAINT = "Image Inpaint or Outpaint"
    IMG_PROMPT = "Image Prompt"
    IMG_ENHANCE = "Image Enhancement"
    NOT_FOUND = "Not Found"


class TaskStatus(str, Enum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class GenerationFinishReason(str, Enum):
    SUCCESS = "SUCCESS"
    QUEUE_IS_FULL = "QUEUE_IS_FULL"
    USER_CANCEL = "USER_CANCEL"
    ERROR = "ERROR"


@dataclass
class ImageGenerationResult:
    """Single generated image result."""
    im: str | None = None
    seed: str = ""
    finish_reason: GenerationFinishReason = GenerationFinishReason.SUCCESS


@dataclass
class QueueTask:
    """Tracks one generation job through the queue lifecycle."""
    job_id: str
    task_type: TaskType
    req_param: dict[str, Any]
    webhook_url: str | None = None
    is_finished: bool = False
    finish_progress: int = 0
    in_queue_mills: int = field(default_factory=lambda: int(time.time() * 1000))
    start_mills: int = 0
    finish_mills: int = 0
    finish_with_error: bool = False
    task_status: str | None = None
    task_step_preview: str | None = None
    task_result: list[ImageGenerationResult] | None = None
    error_message: str | None = None

    def set_progress(self, progress: int, status: str | None = None) -> None:
        self.finish_progress = max(0, min(progress, 100))
        if status is not None:
            self.task_status = status

    def set_step_preview(self, preview: str) -> None:
        self.task_step_preview = preview

    def set_result(
        self,
        result: list[ImageGenerationResult],
        finish_with_error: bool = False,
        error_message: str | None = None,
    ) -> None:
        self.task_result = result
        self.finish_with_error = finish_with_error
        self.error_message = error_message
        if not finish_with_error:
            self.finish_progress = 100
            self.task_status = "Finished"
        else:
            self.task_status = "Error"


@dataclass
class AsyncTask:
    """Holds all parameters for one generation job.

    Constructed from ImageGenerationParams (V1/V2 request).
    """
    prompt: str = ""
    negative_prompt: str = ""
    style_selections: list[str] = field(default_factory=list)
    performance_selection: str = "Speed"
    aspect_ratios_selection: str = "1024×1024"
    image_number: int = 1
    output_format: str = "png"
    seed: str = ""
    read_wildcards_in_order: bool = False
    sharpness: float = 2.0
    guidance_scale: float = 4.0
    base_model_name: str = ""
    refiner_model_name: str = ""
    refiner_switch: float = 0.5
    loras: list[dict[str, Any]] = field(default_factory=list)

    # Image input
    input_image_checkbox: bool = False
    current_tab: str = "prompt"
    uov_method: str | None = None
    uov_input_image: str | None = None
    upscale_value: float | None = None
    outpaint_selections: list[str] = field(default_factory=list)
    inpaint_input_image: dict[str, str] | None = None
    inpaint_additional_prompt: str | None = None
    inpaint_mask_image_upload: str | None = None
    inpaint_negative_prompt: str = ""
    inpaint_respective_field: float = 0.5
    inpaint_strength: float = 1.0
    inpaint_erode_or_dilate: int = 0
    inpaint_mask_upload_overlay: float = 0.0
    inpaint_mask_model: str | None = None

    # Advanced
    disable_preview: bool = False
    disable_intermediate_results: bool = False
    disable_seed_increment: bool = False
    black_out_nsfw: bool = False
    adm_scaler_positive: float = 1.5
    adm_scaler_negative: float = 0.8
    adm_scaler_end: float = 0.3
    adaptive_cfg: float = 7.0
    clip_skip: int = 2
    sampler_name: str = "dpmpp_2m_ssd_gpu"
    scheduler_name: str = "karras"
    vae_name: str | None = None
    overwrite_step: int = -1
    overwrite_switch: int = -1
    overwrite_width: int = -1
    overwrite_height: int = -1
    overwrite_vary_strength: float = -1
    mixing_image_prompt_and_inpaint: str = ""
    mixing_image_prompt_and_outpaint: str = ""
    mixing_image_prompt_and_vary_upscale: str = ""
    debugging_cn_preprocessor: bool = False
    skipping_cn_preprocessor: bool = False
    canny_low_threshold: int = 100
    canny_high_threshold: int = 200
    refiner_swap_method: str = "joint"
    controlnet_softness: float = 0.25
    freeu_enabled: bool = False
    freeu_b1: float = 1.01
    freeu_b2: float = 1.02
    freeu_s1: float = 0.99
    freeu_s2: float = 0.95
    debugging_inpaint_preprocessor: bool = False
    inpaint_disable_initial_latent: bool = False
    inpaint_engine: str = "v2.6"
    inpaint_mask_use_xor: bool = False
    save_final_enhanced_image_only: bool = True
    save_metadata_to_images: bool = False
    metadata_scheme: str = "fooocus"

    # V2: invert mask support
    invert_mask_checkbox: bool = False

    # V2: IP-Adapter FaceID support
    ip_adapter_faceid_embeds: list[list[float]] | None = None
    ip_adapter_faceid_weight: float = 0.8

    # ControlNet tasks: {cn_type: [[img, stop, weight], ...]}
    cn_tasks: dict[str, list[list[Any]]] = field(default_factory=dict)

    # Image prompts (IP-Adapter)
    image_prompts: list[dict[str, Any]] = field(default_factory=list)

    # Enhance
    enhance_input_image: str | None = None
    enhance_checkbox: bool = False
    enhance_uov_method: str | None = None
    enhance_uov_processing_order: str = "Before First Enhancement"
    enhance_uov_prompt_type: str = "Same to Detailed Prompt"
    enhance_ctrlnets: list[Any] = field(default_factory=list)
    should_enhance: bool = False
    images_to_enhance_count: int = 0
    enhance_stats: dict[str, Any] = field(default_factory=dict)
    debugging_enhance_masks_checkbox: bool = False
    debugging_dino: bool = False
    dino_erode_or_dilate: int = 0

    # Outpaint distances
    outpaint_distance_left: int = 0
    outpaint_distance_top: int = 0
    outpaint_distance_right: int = 0
    outpaint_distance_bottom: int = 0

    # Webhook
    webhook_url: str | None = None
    require_base64: bool = False


class TaskOutputs:
    """Collects progress and result outputs during processing."""

    def __init__(self, task: QueueTask) -> None:
        self.task = task
        self.outputs: list[Any] = []

    def append(self, args: tuple) -> None:
        self.outputs.append(args)
        if args[0] == "preview":
            progress = args[1][0] if isinstance(args[1], (list, tuple)) else 0
            text = args[1][1] if isinstance(args[1], (list, tuple)) and len(args[1]) > 1 else ""
            self.task.set_progress(progress, text)
            if len(args[1]) > 2 and args[1][2] is not None:
                self.task.set_step_preview(str(args[1][2]))
