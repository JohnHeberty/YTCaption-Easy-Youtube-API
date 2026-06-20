from __future__ import annotations

from enum import IntEnum, Enum

# =============================================================================
# Seed
# =============================================================================
MIN_SEED = 0
MAX_SEED = 2**63 - 1

# =============================================================================
# Aspect Ratios (SDXL)
# =============================================================================
SDXL_ASPECT_RATIOS = [
    '704*1408', '704*1344', '768*1344', '768*1280', '832*1216', '832*1152',
    '896*1152', '896*1088', '960*1088', '960*1024', '1024*1024', '1024*960',
    '1088*960', '1088*896', '1152*896', '1152*832', '1216*832', '1280*768',
    '1344*768', '1344*704', '1408*704', '1472*704', '1536*640', '1600*640',
    '1664*576', '1728*576'
]

DEFAULT_ASPECT_RATIO = '1152*896'

# =============================================================================
# Samplers
# =============================================================================
KSAMPLER = {
    "euler": "Euler",
    "euler_ancestral": "Euler a",
    "heun": "Heun",
    "heunpp2": "",
    "dpm_2": "DPM2",
    "dpm_2_ancestral": "DPM2 a",
    "lms": "LMS",
    "dpm_fast": "DPM fast",
    "dpm_adaptive": "DPM adaptive",
    "dpmpp_2s_ancestral": "DPM++ 2S a",
    "dpmpp_sde": "DPM++ SDE",
    "dpmpp_sde_gpu": "DPM++ SDE",
    "dpmpp_2m": "DPM++ 2M",
    "dpmpp_2m_sde": "DPM++ 2M SDE",
    "dpmpp_2m_sde_gpu": "DPM++ 2M SDE",
    "dpmpp_3m_sde": "",
    "dpmpp_3m_sde_gpu": "",
    "ddpm": "",
    "lcm": "LCM",
    "tcd": "TCD",
    "restart": "Restart"
}

SAMPLER_EXTRA = {
    "ddim": "DDIM",
    "uni_pc": "UniPC",
    "uni_pc_bh2": ""
}

SAMPLERS = KSAMPLER | SAMPLER_EXTRA

KSAMPLER_NAMES = list(KSAMPLER.keys())
SAMPLER_NAMES = KSAMPLER_NAMES + list(SAMPLER_EXTRA.keys())

SCHEDULER_NAMES = [
    "normal", "karras", "exponential", "sgm_uniform", "simple",
    "ddim_uniform", "lcm", "turbo", "align_your_steps", "tcd",
    "edm_playground_v2.5"
]

CIVITAI_NO_KARRAS = ["euler", "euler_ancestral", "heun", "dpm_fast", "dpm_adaptive", "ddim", "uni_pc"]

# =============================================================================
# Defaults
# =============================================================================
DEFAULT_PERFORMANCE = 'Speed'
DEFAULT_CFG_SCALE = 4.0
DEFAULT_SHARPNESS = 2.0
DEFAULT_GUIDANCE_SCALE = 7.0
DEFAULT_CLIP_SKIP = 2
DEFAULT_VAE = 'Default (model)'
DEFAULT_REFINER_SWAP = 'joint'
DEFAULT_BASE_MODEL = 'juggernautXL_v8Rundiffusion.safetensors'
DEFAULT_REFINER_MODEL = 'None'

DEFAULT_LORAS = [
    {"enabled": True, "model_name": "sd_xl_offset_example-lora_1.0.safetensors", "weight": 0.1},
    {"enabled": True, "model_name": "None", "weight": 1.0},
    {"enabled": True, "model_name": "None", "weight": 1.0},
    {"enabled": True, "model_name": "None", "weight": 1.0},
    {"enabled": True, "model_name": "None", "weight": 1.0},
]

DEFAULT_STYLE_SELECTIONS = ["Fooocus V2", "Fooocus Enhance", "Fooocus Sharp"]

# =============================================================================
# ControlNet
# =============================================================================
CN_IP = "ImagePrompt"
CN_IP_FACE = "FaceSwap"
CN_CANNY = "PyraCanny"
CN_CPDS = "CPDS"

IP_LIST = [CN_IP, CN_CANNY, CN_CPDS, CN_IP_FACE]

DEFAULT_IP_PARAMETERS = {
    CN_IP: (0.5, 0.6),
    CN_IP_FACE: (0.9, 0.75),
    CN_CANNY: (0.5, 1.0),
    CN_CPDS: (0.5, 1.0),
}

# =============================================================================
# Inpaint
# =============================================================================
INPAINT_MASK_MODELS = [
    'u2net', 'u2netp', 'u2net_human_seg', 'u2net_cloth_seg',
    'silueta', 'isnet-general-use', 'isnet-anime', 'sam'
]

INPAINT_MASK_CLOTH_CATEGORY = ['full', 'upper', 'lower']
INPAINT_MASK_SAM_MODEL = ['vit_b', 'vit_l', 'vit_h']

INPAINT_ENGINE_VERSIONS = ['None', 'v1', 'v2.5', 'v2.6']

INPAINT_OPTION_DEFAULT = 'Inpaint or Outpaint (default)'
INPAINT_OPTION_DETAIL = 'Improve Detail (face, hand, eyes, etc.)'
INPAINT_OPTION_MODIFY = 'Modify Content (add objects, change background, etc.)'
INPAINT_OPTIONS = [INPAINT_OPTION_DEFAULT, INPAINT_OPTION_DETAIL, INPAINT_OPTION_MODIFY]

# =============================================================================
# Describe Image
# =============================================================================
DESCRIBE_TYPE_PHOTO = 'Photograph'
DESCRIBE_TYPE_ANIME = 'Art/Anime'
DESCRIBE_TYPES = [DESCRIBE_TYPE_PHOTO, DESCRIBE_TYPE_ANIME]

# =============================================================================
# Output
# =============================================================================
OUTPUT_FORMATS = ['png', 'jpeg', 'webp']
DEFAULT_OUTPUT_FORMAT = 'png'

AUTH_FILENAME = 'auth.json'

# =============================================================================
# Input Image Tabs
# =============================================================================
INPUT_IMAGE_TAB_IDS = [
    'uov_tab', 'ip_tab', 'inpaint_tab',
    'describe_tab', 'enhance_tab', 'metadata_tab'
]

# =============================================================================
# Enhancement UOV
# =============================================================================
ENHANCEMENT_UOV_BEFORE = "Before First Enhancement"
ENHANCEMENT_UOV_AFTER = "After Last Enhancement"
ENHANCEMENT_UOV_PROCESSING_ORDER = [ENHANCEMENT_UOV_BEFORE, ENHANCEMENT_UOV_AFTER]

ENHANCEMENT_UOV_PROMPT_TYPE_ORIGINAL = 'Original Prompts'
ENHANCEMENT_UOV_PROMPT_TYPE_LAST_FILLED = 'Last Filled Enhancement Prompts'
ENHANCEMENT_UOV_PROMPT_TYPES = [ENHANCEMENT_UOV_PROMPT_TYPE_ORIGINAL, ENHANCEMENT_UOV_PROMPT_TYPE_LAST_FILLED]

# =============================================================================
# Performance Modes
# =============================================================================
class PerformanceLoRA(Enum):
    QUALITY = None
    SPEED = None
    EXTREME_SPEED = 'sdxl_lcm_lora.safetensors'
    LIGHTNING = 'sdxl_lightning_4step_lora.safetensors'
    HYPER_SD = 'sdxl_hyper_sd_4step_lora.safetensors'


class Steps(IntEnum):
    QUALITY = 60
    SPEED = 30
    EXTREME_SPEED = 8
    LIGHTNING = 4
    HYPER_SD = 4


class StepsUOV(IntEnum):
    QUALITY = 36
    SPEED = 18
    EXTREME_SPEED = 8
    LIGHTNING = 4
    HYPER_SD = 4
