from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Request / Response Enums
# =============================================================================

class PerformanceSelection(str):
    speed = "Speed"
    quality = "Quality"
    extreme_speed = "Extreme Speed"
    lightning = "Lightning"
    hyper_sd = "Hyper-SD"


class UpscaleOrVaryMethod(str):
    disabled = "Disabled"
    subtle_variation = "Vary (Subtle)"
    strong_variation = "Vary (Strong)"
    upscale_15 = "Upscale (1.5x)"
    upscale_2 = "Upscale (2x)"
    upscale_fast = "Upscale (Fast 2x)"
    upscale_custom = "Upscale (Custom)"


class OutpaintExpansion(str):
    left = "Left"
    right = "Right"
    top = "Top"
    bottom = "Bottom"


class ControlNetType(str):
    cn_ip = "ImagePrompt"
    cn_ip_face = "FaceSwap"
    cn_canny = "PyraCanny"
    cn_cpds = "CPDS"
    cn_openpose = "OpenPose"


class MaskModel(str):
    u2net = "u2net"
    u2netp = "u2netp"
    u2net_human_seg = "u2net_human_seg"
    u2net_cloth_seg = "u2net_cloth_seg"
    silueta = "silueta"
    isnet_general_use = "isnet-general-use"
    isnet_anime = "isnet-anime"
    sam = "sam"


class DescribeImageType(str):
    photo = "Photo"
    anime = "Anime"


# =============================================================================
# Common sub-models
# =============================================================================

class Lora(BaseModel):
    enabled: bool = Field(default=True, description="Enable this LoRA")
    model_name: str = Field(default="None", description="LoRA model filename")
    weight: float = Field(default=0.5, ge=-2, le=2, description="LoRA weight (-2 to 2)")
    model_config = ConfigDict(protected_namespaces=())


class AdvancedParams(BaseModel):
    disable_preview: bool = Field(default=False, description="Disable preview image during generation")
    disable_intermediate_results: bool = Field(default=False, description="Disable intermediate results output")
    disable_seed_increment: bool = Field(default=False, description="Disable seed auto-increment between images")
    adm_scaler_positive: float = Field(1.5, ge=0.1, le=3.0, description="ADM scaler positive guidance")
    adm_scaler_negative: float = Field(0.8, ge=0.1, le=3.0, description="ADM scaler negative guidance")
    adm_scaler_end: float = Field(0.3, ge=0.0, le=1.0, description="ADM scaler end step fraction")
    adaptive_cfg: float = Field(7.0, ge=1.0, le=30.0, description="Adaptive CFG value")
    clip_skip: int = Field(2, ge=1, le=12, description="CLIP text encoder skip layers")
    sampler_name: str = Field(default="dpmpp_2m_ssd_gpu", description="Diffusion sampler name")
    scheduler_name: str = Field(default="karras", description="Noise scheduler name")
    overwrite_step: int = Field(-1, ge=-1, le=200, description="Override diffusion steps (-1 = use default)")
    overwrite_switch: float = Field(-1, ge=-1, le=1, description="Override refiner switch step (-1 = use default)")
    overwrite_width: int = Field(-1, ge=-1, le=2048, description="Override output width (-1 = use aspect ratio)")
    overwrite_height: int = Field(-1, ge=-1, le=2048, description="Override output height (-1 = use aspect ratio)")
    overwrite_vary_strength: float = Field(-1, ge=-1, le=1.0, description="Override variation strength (-1 = use default)")
    overwrite_upscale_strength: float = Field(-1, ge=-1, le=1.0, description="Override upscale strength (-1 = use default)")
    mixing_image_prompt_and_vary_upscale: bool = Field(default=False, description="Mix image prompt with vary/upscale")
    mixing_image_prompt_and_inpaint: bool = Field(default=False, description="Mix image prompt with inpaint")
    debugging_cn_preprocessor: bool = Field(default=False, description="Enable ControlNet preprocessor debug output")
    skipping_cn_preprocessor: bool = Field(default=False, description="Skip ControlNet preprocessor")
    canny_low_threshold: int = Field(64, ge=1, le=255, description="Canny edge low threshold")
    canny_high_threshold: int = Field(128, ge=1, le=255, description="Canny edge high threshold")
    refiner_swap_method: str = Field(default="joint", description="Refiner swap method")
    controlnet_softness: float = Field(0.25, ge=0.0, le=1.0, description="ControlNet softness factor")
    freeu_enabled: bool = Field(default=False, description="Enable FreeU for quality improvement")
    freeu_b1: float = Field(default=1.01, description="FreeU skip connection B1 factor")
    freeu_b2: float = Field(default=1.02, description="FreeU skip connection B2 factor")
    freeu_s1: float = Field(default=0.99, description="FreeU skip connection S1 factor")
    freeu_s2: float = Field(default=0.95, description="FreeU skip connection S2 factor")
    debugging_inpaint_preprocessor: bool = Field(default=False, description="Enable inpaint preprocessor debug output")
    inpaint_disable_initial_latent: bool = Field(default=False, description="Disable initial latent in inpainting")
    inpaint_engine: str = Field(default="v2.6", description="Inpaint engine version")
    inpaint_strength: float = Field(1.0, ge=0.0, le=1.0, description="Inpaint strength (0-1)")
    inpaint_respective_field: float = Field(0.618, ge=0.0, le=1.0, description="Inpaint respective field ratio")
    inpaint_advanced_masking_checkbox: bool = Field(default=True, description="Enable advanced inpaint masking")
    invert_mask_checkbox: bool = Field(default=False, description="Invert inpaint mask")
    inpaint_erode_or_dilate: int = Field(0, ge=-64, le=64, description="Inpaint mask erode/dilate (-64 to 64)")
    black_out_nsfw: bool = Field(default=False, description="Black out NSFW detected areas")
    vae_name: str = Field(default="Automatic", description="VAE model name")
    debugging_dino: bool = Field(default=False, description="Enable DINO debug output")
    dino_erode_or_dilate: int = Field(0, ge=-64, le=64, description="DINO mask erode/dilate (-64 to 64)")
    debugging_enhance_masks_checkbox: bool = Field(default=False, description="Enable enhance mask debug output")


class EnhanceCtrlNets(BaseModel):
    enhance_enabled: bool = Field(default=False, description="Enable enhancement pipeline")
    enhance_mask_dino_prompt: str = Field(default="face", description="DINO detection prompt for mask")
    enhance_prompt: str = Field(default="", description="Enhancement prompt")
    enhance_negative_prompt: str = Field(default="", description="Enhancement negative prompt")
    enhance_mask_model: str = Field(default="sam", description="Mask generation model")
    enhance_mask_cloth_category: str = Field(default="full", description="Cloth segmentation category")
    enhance_mask_sam_model: str = Field(default="vit_b", description="SAM model variant")
    enhance_mask_text_threshold: float = Field(0.25, ge=0, le=1, description="DINO text confidence threshold")
    enhance_mask_box_threshold: float = Field(0.3, ge=0, le=1, description="DINO box confidence threshold")
    enhance_mask_sam_max_detections: int = Field(0, ge=0, le=10, description="Max SAM detections (0 = unlimited)")
    enhance_inpaint_disable_initial_latent: bool = Field(default=False, description="Disable initial latent for enhance inpaint")
    enhance_inpaint_engine: str = Field(default="v2.6", description="Enhance inpaint engine version")
    enhance_inpaint_strength: float = Field(1, ge=0, le=1, description="Enhance inpaint strength")
    enhance_inpaint_respective_field: float = Field(0.618, ge=0, le=1, description="Enhance inpaint respective field")
    enhance_inpaint_erode_or_dilate: float = Field(0, ge=-64, le=64, description="Enhance mask erode/dilate")
    enhance_mask_invert: bool = Field(default=False, description="Invert enhance mask")


# =============================================================================
# V2 JSON models (image_prompts)
# =============================================================================

class ImagePromptJson(BaseModel):
    cn_img: str | None = Field(None, description="Base64-encoded ControlNet image")
    cn_stop: float | None = Field(0, ge=0, le=1, description="ControlNet stop step (0-1)")
    cn_weight: float | None = Field(0, ge=0, le=2, description="ControlNet weight (0-2)")
    cn_type: str = Field(default="ImagePrompt", description="ControlNet type")


# =============================================================================
# CommonRequest — base for all generation requests (V2 JSON)
# =============================================================================

DEFAULT_LORAS = [
    Lora(enabled=True, model_name="sd_xl_offset_example-lora_1.0.safetensors", weight=0.1),
    Lora(enabled=True, model_name="None", weight=1.0),
    Lora(enabled=True, model_name="None", weight=1.0),
    Lora(enabled=True, model_name="None", weight=1.0),
    Lora(enabled=True, model_name="None", weight=1.0),
]


class CommonRequest(BaseModel):
    prompt: str = Field(default="", description="Text prompt for image generation")
    negative_prompt: str = Field(default="", description="Negative prompt to avoid unwanted features")
    style_selections: list[str] = Field(
        default_factory=lambda: ["Fooocus V2", "Fooocus Enhance", "Fooocus Sharp"],
        description="Active style presets",
    )
    performance_selection: str = Field(default="Speed", description="Performance mode: Speed, Quality, Extreme Speed, Lightning, Hyper-SD")
    aspect_ratios_selection: str = Field(default="1152*896", description="Output aspect ratio (WxH)")
    image_number: int = Field(default=1, ge=1, le=32, description="Number of images to generate")
    image_seed: int = Field(default=-1, description="Random seed (-1 for random)")
    sharpness: float = Field(default=2.0, ge=0.0, le=30.0, description="Sharpening strength")
    guidance_scale: float = Field(default=4.0, ge=1.0, le=30.0, description="CFG guidance scale")
    base_model_name: str = Field(default="juggernautXL_v8Rundiffusion.safetensors", description="Base SDXL model filename")
    refiner_model_name: str = Field(default="None", description="Refiner model filename")
    refiner_switch: float = Field(default=0.5, ge=0.1, le=1.0, description="Refiner switch step fraction")
    loras: list[Lora] = Field(default_factory=lambda: DEFAULT_LORAS, description="LoRA model configurations")
    advanced_params: AdvancedParams | None = Field(default=None, description="Advanced generation parameters")
    save_meta: bool = Field(default=True, description="Save metadata to output images")
    meta_scheme: str = Field(default="fooocus", description="Metadata scheme: 'fooocus' or 'comfy'")
    save_extension: str = Field(default="png", description="Output format: png, jpeg, webp")
    save_name: str = Field(default="", description="Custom filename prefix")
    read_wildcards_in_order: bool = Field(default=False, description="Read wildcards in sequential order")
    require_base64: bool = Field(default=False, description="Return base64-encoded images in response")
    async_process: bool = Field(default=False, description="Process asynchronously (returns job_id)")
    webhook_url: str | None = Field(default="", description="Webhook URL for async completion callback")

    @classmethod
    def as_form(cls, prompt: str = "", negative_prompt: str = "", **kwargs: Any) -> CommonRequest:
        return cls(prompt=prompt, negative_prompt=negative_prompt, **kwargs)


# =============================================================================
# V1 Generation Request Models (for OpenAPI docs — actual proxy uses raw body)
# =============================================================================

class TextToImageRequest(CommonRequest):
    pass


class ImgUpscaleVaryRequest(CommonRequest):
    input_image: str = Field(default="", description="Base64 or URL input image")
    uov_method: str = Field(default="Upscale (1.5x)", description="Upscale/vary method")
    upscale_value: float | None = Field(None, ge=1.0, le=5.0, description="Custom upscale factor (1-5x)")


ImgUpscaleOrVaryRequest = ImgUpscaleVaryRequest


class ImgInpaintOrOutpaintRequest(CommonRequest):
    input_image: str = Field(default="", description="Base64 or URL input image")
    input_mask: str | None = Field(default="", description="Base64 or URL mask image")
    inpaint_additional_prompt: str | None = Field(default="", description="Additional inpainting prompt")
    outpaint_selections: list[str] = Field(default_factory=list, description="Outpaint directions: Left, Right, Top, Bottom")
    outpaint_distance_left: int | None = Field(default=-1, description="Outpaint left distance pixels (-1 = default)")
    outpaint_distance_right: int | None = Field(default=-1, description="Outpaint right distance pixels (-1 = default)")
    outpaint_distance_top: int | None = Field(default=-1, description="Outpaint top distance pixels (-1 = default)")
    outpaint_distance_bottom: int | None = Field(default=-1, description="Outpaint bottom distance pixels (-1 = default)")
    image_prompts: list[ImagePromptJson] = Field(default_factory=list, description="ControlNet image prompts")


class ImgPromptRequest(ImgInpaintOrOutpaintRequest):
    image_prompts: list[ImagePromptJson] = Field(default_factory=list, description="ControlNet image prompts")


class ImageEnhanceRequest(CommonRequest):
    enhance_input_image: str = Field(default="", description="Base64 or URL image to enhance")
    enhance_checkbox: bool = Field(default=True, description="Enable enhancement pipeline")
    enhance_uov_method: str = Field(default="Vary (Strong)", description="Enhancement upscale/vary method")
    enhance_uov_processing_order: str = Field(default="Before First Enhancement", description="Processing order relative to enhancements")
    enhance_uov_prompt_type: str = Field(default="Original Prompts", description="Prompt type for UOV during enhancement")
    save_final_enhanced_image_only: bool = Field(default=True, description="Save only final enhanced image")
    enhance_ctrlnets: list[EnhanceCtrlNets] = Field(default_factory=list, description="Enhancement ControlNet configs")


# =============================================================================
# V2 Generation Request Models (JSON with image_prompts)
# =============================================================================

class Text2ImgRequestWithPrompt(CommonRequest):
    image_prompts: list[ImagePromptJson] = Field(default_factory=list, description="ControlNet image prompts")


class ImgUpscaleOrVaryRequestJson(CommonRequest):
    uov_method: str = Field(default="Upscale (2x)", description="Upscale/vary method")
    upscale_value: float | None = Field(1.0, ge=1.0, le=5.0, description="Custom upscale factor (1-5x)")
    input_image: str = Field(default="", description="Base64 or URL input image")
    image_prompts: list[ImagePromptJson] = Field(default_factory=list, description="ControlNet image prompts")


class ImgInpaintOrOutpaintRequestJson(CommonRequest):
    input_image: str = Field(default="", description="Base64 or URL input image")
    input_mask: str | None = Field(default="", description="Base64 or URL mask image")
    inpaint_additional_prompt: str | None = Field(default="", description="Additional inpainting prompt")
    outpaint_selections: list[str] = Field(default_factory=list, description="Outpaint directions")
    outpaint_distance_left: int | None = Field(default=-1, description="Outpaint left distance pixels")
    outpaint_distance_right: int | None = Field(default=-1, description="Outpaint right distance pixels")
    outpaint_distance_top: int | None = Field(default=-1, description="Outpaint top distance pixels")
    outpaint_distance_bottom: int | None = Field(default=-1, description="Outpaint bottom distance pixels")
    image_prompts: list[Any] = Field(default_factory=list, description="ControlNet image prompts")


class ImgPromptRequestJson(ImgInpaintOrOutpaintRequestJson):
    image_prompts: list[ImagePromptJson] = Field(default_factory=list, description="ControlNet image prompts")


class ImageEnhanceRequestJson(CommonRequest):
    enhance_input_image: str = Field(default="", description="Base64 or URL image to enhance")
    enhance_checkbox: bool = Field(default=True, description="Enable enhancement pipeline")
    enhance_uov_method: str = Field(default="Vary (Strong)", description="Enhancement upscale/vary method")
    enhance_uov_processing_order: str = Field(default="Before First Enhancement", description="Processing order relative to enhancements")
    enhance_uov_prompt_type: str = Field(default="Original Prompts", description="Prompt type for UOV during enhancement")
    save_final_enhanced_image_only: bool = Field(default=True, description="Save only final enhanced image")
    enhance_ctrlnets: list[EnhanceCtrlNets] = Field(default_factory=list, description="Enhancement ControlNet configs")


# =============================================================================
# Tools Request Models
# =============================================================================

class GenerateMaskRequest(BaseModel):
    image: str = Field(..., description="Image URL or base64-encoded image")
    mask_model: str = Field(default="isnet-general-use", description="Mask model: u2net, u2netp, u2net_human_seg, u2net_cloth_seg, silueta, isnet-general-use, isnet-anime, sam")
    cloth_category: str = Field(default="full", description="Cloth category for u2net_cloth_seg: full, upper, lower")
    dino_prompt_text: str = Field(default="", description="DINO text prompt for SAM detection")
    sam_model: str = Field(default="vit_b", description="SAM model variant: vit_b, vit_l, vit_h")
    box_threshold: float = Field(0.3, ge=0, le=1, description="DINO box confidence threshold")
    text_threshold: float = Field(0.25, ge=0, le=1, description="DINO text confidence threshold")
    sam_max_detections: int = Field(0, ge=0, le=10, description="Max SAM detections (0 = unlimited)")
    dino_erode_or_dilate: float = Field(0, ge=-64, le=64, description="DINO mask erode/dilate")
    dino_debug: bool = Field(default=False, description="Enable DINO debug visualization")


class DescribeImageRequest(BaseModel):
    image: str = Field(..., description="Base64-encoded image")


# =============================================================================
# Response Models
# =============================================================================

class GeneratedImageResult(BaseModel):
    base64: str | None = Field(None, description="Base64-encoded image data")
    url: str | None = Field(None, description="Relative URL to download the image")
    seed: str = Field(default="", description="Random seed used for generation")
    finish_reason: str = Field(default="", description="Generation finish reason")


class AsyncJobResponse(BaseModel):
    job_id: str = Field(default="", description="Unique job identifier")
    job_type: str = Field(default="", description="Type of generation job")
    job_stage: str = Field(default="WAITING", description="Current stage: WAITING, RUNNING, SUCCESS, ERROR")
    job_progress: int = Field(default=0, description="Progress percentage (0-100)")
    job_status: str | None = Field(None, description="Human-readable status message")
    job_step_preview: str | None = Field(None, description="Base64 preview of current step")
    job_result: Any | None = Field(None, description="Generation results (list of GeneratedImageResult)")


class JobStatus(BaseModel):
    job_id: str = Field(..., description="Unique job identifier")
    job_type: str = Field(default="", description="Type of generation job")
    job_stage: str = Field(default="", description="Current stage")
    job_progress: int = Field(default=0, description="Progress percentage")
    job_status: str | None = Field(None, description="Status message")
    job_step_preview: str | None = Field(None, description="Step preview image")
    job_result: Any | None = Field(None, description="Job results")


class DescribeImageResponse(BaseModel):
    describe: str = Field(..., description="Image description/tags")


class StopResponse(BaseModel):
    msg: str = Field(..., description="Stop confirmation message")


class JobQueueInfo(BaseModel):
    running_size: int = Field(..., description="Number of currently running jobs")
    finished_size: int = Field(..., description="Number of finished jobs in history")
    last_job_id: str | None = Field(None, description="Most recent job ID")


class JobHistoryInfo(BaseModel):
    job_id: str = Field(..., description="Job identifier")
    in_queue_mills: int = Field(..., description="Timestamp when queued (epoch ms)")
    start_mills: int = Field(..., description="Timestamp when started (epoch ms)")
    finish_mills: int = Field(..., description="Timestamp when finished (epoch ms)")
    is_finished: bool = Field(default=False, description="Whether job has completed")


class JobHistoryResponse(BaseModel):
    queue: list[JobHistoryInfo] = Field(default_factory=list, description="Currently queued jobs")
    history: list[JobHistoryInfo] = Field(default_factory=list, description="Completed jobs")


class AllModelNamesResponse(BaseModel):
    model_filenames: list[str] = Field(..., description="Available base model filenames")
    lora_filenames: list[str] = Field(..., description="Available LoRA model filenames")


class QueryJobRequest(BaseModel):
    job_id: str = Field(..., description="Job identifier to query")
    require_step_preview: bool = Field(default=False, description="Include step preview in response")
