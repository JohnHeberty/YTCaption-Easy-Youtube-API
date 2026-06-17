from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any


# =============================================================================
# Enums (matching FOOOCUS)
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
    enabled: bool = True
    model_name: str = "None"
    weight: float = Field(default=0.5, ge=-2, le=2)
    model_config = ConfigDict(protected_namespaces=())


class AdvancedParams(BaseModel):
    disable_preview: bool = False
    disable_intermediate_results: bool = False
    disable_seed_increment: bool = False
    adm_scaler_positive: float = Field(1.5, ge=0.1, le=3.0)
    adm_scaler_negative: float = Field(0.8, ge=0.1, le=3.0)
    adm_scaler_end: float = Field(0.3, ge=0.0, le=1.0)
    adaptive_cfg: float = Field(7.0, ge=1.0, le=30.0)
    clip_skip: int = Field(2, ge=1, le=12)
    sampler_name: str = "dpmpp_2m_ssd_gpu"
    scheduler_name: str = "karras"
    overwrite_step: int = Field(-1, ge=-1, le=200)
    overwrite_switch: float = Field(-1, ge=-1, le=1)
    overwrite_width: int = Field(-1, ge=-1, le=2048)
    overwrite_height: int = Field(-1, ge=-1, le=2048)
    overwrite_vary_strength: float = Field(-1, ge=-1, le=1.0)
    overwrite_upscale_strength: float = Field(-1, ge=-1, le=1.0)
    mixing_image_prompt_and_vary_upscale: bool = False
    mixing_image_prompt_and_inpaint: bool = False
    debugging_cn_preprocessor: bool = False
    skipping_cn_preprocessor: bool = False
    canny_low_threshold: int = Field(64, ge=1, le=255)
    canny_high_threshold: int = Field(128, ge=1, le=255)
    refiner_swap_method: str = "joint"
    controlnet_softness: float = Field(0.25, ge=0.0, le=1.0)
    freeu_enabled: bool = False
    freeu_b1: float = 1.01
    freeu_b2: float = 1.02
    freeu_s1: float = 0.99
    freeu_s2: float = 0.95
    debugging_inpaint_preprocessor: bool = False
    inpaint_disable_initial_latent: bool = False
    inpaint_engine: str = "v2.6"
    inpaint_strength: float = Field(1.0, ge=0.0, le=1.0)
    inpaint_respective_field: float = Field(0.618, ge=0.0, le=1.0)
    inpaint_advanced_masking_checkbox: bool = True
    invert_mask_checkbox: bool = False
    inpaint_erode_or_dilate: int = Field(0, ge=-64, le=64)
    black_out_nsfw: bool = False
    vae_name: str = "Automatic"
    debugging_dino: bool = False
    dino_erode_or_dilate: int = Field(0, ge=-64, le=64)
    debugging_enhance_masks_checkbox: bool = False


class EnhanceCtrlNets(BaseModel):
    enhance_enabled: bool = False
    enhance_mask_dino_prompt: str = "face"
    enhance_prompt: str = ""
    enhance_negative_prompt: str = ""
    enhance_mask_model: str = "sam"
    enhance_mask_cloth_category: str = "full"
    enhance_mask_sam_model: str = "vit_b"
    enhance_mask_text_threshold: float = Field(0.25, ge=0, le=1)
    enhance_mask_box_threshold: float = Field(0.3, ge=0, le=1)
    enhance_mask_sam_max_detections: int = Field(0, ge=0, le=10)
    enhance_inpaint_disable_initial_latent: bool = False
    enhance_inpaint_engine: str = "v2.6"
    enhance_inpaint_strength: float = Field(1, ge=0, le=1)
    enhance_inpaint_respective_field: float = Field(0.618, ge=0, le=1)
    enhance_inpaint_erode_or_dilate: float = Field(0, ge=-64, le=64)
    enhance_mask_invert: bool = False


# =============================================================================
# V2 JSON models (image_prompts)
# =============================================================================

class ImagePromptJson(BaseModel):
    cn_img: Optional[str] = Field(None, description="base64 image")
    cn_stop: Optional[float] = Field(0, ge=0, le=1)
    cn_weight: Optional[float] = Field(0, ge=0, le=2)
    cn_type: str = "ImagePrompt"


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
    prompt: str = ""
    negative_prompt: str = ""
    style_selections: List[str] = Field(default_factory=lambda: ["Fooocus V2", "Fooocus Enhance", "Fooocus Sharp"])
    performance_selection: str = "Speed"
    aspect_ratios_selection: str = "1152*896"
    image_number: int = Field(default=1, ge=1, le=32)
    image_seed: int = Field(default=-1, description="-1 for random")
    sharpness: float = Field(default=2.0, ge=0.0, le=30.0)
    guidance_scale: float = Field(default=4.0, ge=1.0, le=30.0)
    base_model_name: str = "juggernautXL_v8Rundiffusion.safetensors"
    refiner_model_name: str = "None"
    refiner_switch: float = Field(default=0.5, ge=0.1, le=1.0)
    loras: List[Lora] = Field(default_factory=lambda: DEFAULT_LORAS)
    advanced_params: Optional[AdvancedParams] = None
    save_meta: bool = True
    meta_scheme: str = "fooocus"
    save_extension: str = "png"
    save_name: str = ""
    read_wildcards_in_order: bool = False
    require_base64: bool = False
    async_process: bool = False
    webhook_url: Optional[str] = ""

    @classmethod
    def as_form(cls, prompt: str = "", negative_prompt: str = "", **kwargs):
        return cls(prompt=prompt, negative_prompt=negative_prompt, **kwargs)


# =============================================================================
# V1 Generation Request Models (for OpenAPI docs — actual proxy uses raw body)
# =============================================================================

class TextToImageRequest(CommonRequest):
    pass


class ImgUpscaleVaryRequest(CommonRequest):
    input_image: str = ""
    uov_method: str = "Upscale (1.5x)"
    upscale_value: Optional[float] = Field(None, ge=1.0, le=5.0)


ImgUpscaleOrVaryRequest = ImgUpscaleVaryRequest


class ImgInpaintOrOutpaintRequest(CommonRequest):
    input_image: str = ""
    input_mask: Optional[str] = ""
    inpaint_additional_prompt: Optional[str] = ""
    outpaint_selections: List[str] = []
    outpaint_distance_left: Optional[int] = -1
    outpaint_distance_right: Optional[int] = -1
    outpaint_distance_top: Optional[int] = -1
    outpaint_distance_bottom: Optional[int] = -1


class ImgPromptRequest(ImgInpaintOrOutpaintRequest):
    image_prompts: List[ImagePromptJson] = []


class ImageEnhanceRequest(CommonRequest):
    enhance_input_image: str = ""
    enhance_checkbox: bool = True
    enhance_uov_method: str = "Vary (Strong)"
    enhance_uov_processing_order: str = "Before First Enhancement"
    enhance_uov_prompt_type: str = "Original Prompts"
    save_final_enhanced_image_only: bool = True
    enhance_ctrlnets: List[EnhanceCtrlNets] = []


# =============================================================================
# V2 Generation Request Models (JSON with image_prompts)
# =============================================================================

class Text2ImgRequestWithPrompt(CommonRequest):
    image_prompts: List[ImagePromptJson] = []


class ImgUpscaleOrVaryRequestJson(CommonRequest):
    uov_method: str = "Upscale (2x)"
    upscale_value: Optional[float] = Field(1.0, ge=1.0, le=5.0)
    input_image: str = ""
    image_prompts: List[ImagePromptJson] = []


class ImgInpaintOrOutpaintRequestJson(CommonRequest):
    input_image: str = ""
    input_mask: Optional[str] = ""
    inpaint_additional_prompt: Optional[str] = ""
    outpaint_selections: List[str] = []
    outpaint_distance_left: Optional[int] = -1
    outpaint_distance_right: Optional[int] = -1
    outpaint_distance_top: Optional[int] = -1
    outpaint_distance_bottom: Optional[int] = -1
    image_prompts: List[Any] = []


class ImgPromptRequestJson(ImgInpaintOrOutpaintRequestJson):
    image_prompts: List[ImagePromptJson] = []


class ImageEnhanceRequestJson(CommonRequest):
    enhance_input_image: str = ""
    enhance_checkbox: bool = True
    enhance_uov_method: str = "Vary (Strong)"
    enhance_uov_processing_order: str = "Before First Enhancement"
    enhance_uov_prompt_type: str = "Original Prompts"
    save_final_enhanced_image_only: bool = True
    enhance_ctrlnets: List[EnhanceCtrlNets] = []


# =============================================================================
# Tools Request Models
# =============================================================================

class GenerateMaskRequest(BaseModel):
    image: str = Field(description="Image url or base64")
    mask_model: str = "isnet-general-use"
    cloth_category: str = "full"
    dino_prompt_text: str = ""
    sam_model: str = "vit_b"
    box_threshold: float = Field(0.3, ge=0, le=1)
    text_threshold: float = Field(0.25, ge=0, le=1)
    sam_max_detections: int = Field(0, ge=0, le=10)
    dino_erode_or_dilate: float = Field(0, ge=-64, le=64)
    dino_debug: bool = False


class DescribeImageRequest(BaseModel):
    image: str = Field(description="base64 image")


# =============================================================================
# Response Models
# =============================================================================

class GeneratedImageResult(BaseModel):
    base64: Optional[str] = None
    url: Optional[str] = None
    seed: str = ""
    finish_reason: str = ""


class AsyncJobResponse(BaseModel):
    job_id: str = ""
    job_type: str = ""
    job_stage: str = "WAITING"
    job_progress: int = 0
    job_status: Optional[str] = None
    job_step_preview: Optional[str] = None
    job_result: Optional[Any] = None


class JobStatus(BaseModel):
    job_id: str
    job_type: str = ""
    job_stage: str = ""
    job_progress: int = 0
    job_status: Optional[str] = None
    job_step_preview: Optional[str] = None
    job_result: Optional[Any] = None


class DescribeImageResponse(BaseModel):
    describe: str


class StopResponse(BaseModel):
    msg: str


class JobQueueInfo(BaseModel):
    running_size: int
    finished_size: int
    last_job_id: Optional[str] = None


class JobHistoryInfo(BaseModel):
    job_id: str
    in_queue_mills: int
    start_mills: int
    finish_mills: int
    is_finished: bool = False


class JobHistoryResponse(BaseModel):
    queue: List[JobHistoryInfo] = []
    history: List[JobHistoryInfo] = []


class AllModelNamesResponse(BaseModel):
    model_filenames: List[str]
    lora_filenames: List[str]


class QueryJobRequest(BaseModel):
    job_id: str
    require_step_preview: bool = False
