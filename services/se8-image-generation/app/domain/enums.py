from enum import IntEnum, Enum


# =============================================================================
# Performance
# =============================================================================
class PerformanceSelection(str, Enum):
    QUALITY = "Quality"
    SPEED = "Speed"
    EXTREME_SPEED = "Extreme Speed"
    LIGHTNING = "Lightning"
    HYPER_SD = "Hyper-SD"

    @classmethod
    def list(cls) -> list:
        return [c.value for c in cls]

    def steps(self) -> int:
        from app.core.constants import Steps
        return Steps[self.name].value

    def steps_uov(self) -> int:
        from app.core.constants import StepsUOV
        return StepsUOV[self.name].value

    def lora_filename(self) -> str | None:
        from app.core.constants import PerformanceLoRA
        return PerformanceLoRA[self.name].value


# =============================================================================
# Upscale / Vary
# =============================================================================
class UpscaleOrVaryMethod(str, Enum):
    DISABLED = 'Disabled'
    SUBTLE_VARIATION = 'Vary (Subtle)'
    STRONG_VARIATION = 'Vary (Strong)'
    UPSCALE_15 = 'Upscale (1.5x)'
    UPSCALE_2 = 'Upscale (2x)'
    UPSCALE_FAST = 'Upscale (Fast 2x)'
    UPSCALE_CUSTOM = 'Upscale (Custom)'

    @classmethod
    def list(cls) -> list:
        return [c.value for c in cls]


# =============================================================================
# Outpaint
# =============================================================================
class OutpaintExpansion(str, Enum):
    LEFT = 'Left'
    RIGHT = 'Right'
    TOP = 'Top'
    BOTTOM = 'Bottom'


# =============================================================================
# ControlNet
# =============================================================================
class ControlNetType(str, Enum):
    CN_IP = "ImagePrompt"
    CN_IP_FACE = "FaceSwap"
    CN_CANNY = "PyraCanny"
    CN_CPDS = "CPDS"


# =============================================================================
# Mask Model
# =============================================================================
class MaskModel(str, Enum):
    U2NET = "u2net"
    U2NETP = "u2netp"
    U2NET_HUMAN_SEG = "u2net_human_seg"
    U2NET_CLOTH_SEG = "u2net_cloth_seg"
    SILUETA = "silueta"
    ISNET_GENERAL_USE = "isnet-general-use"
    ISNET_ANIME = "isnet-anime"
    SAM = "sam"


# =============================================================================
# Describe Image Type
# =============================================================================
class DescribeImageType(str, Enum):
    PHOTO = "Photo"
    ANIME = "Anime"


# =============================================================================
# Output Format
# =============================================================================
class OutputFormat(str, Enum):
    PNG = 'png'
    JPEG = 'jpeg'
    WEBP = 'webp'

    @classmethod
    def list(cls) -> list:
        return [c.value for c in cls]


# =============================================================================
# Metadata Scheme
# =============================================================================
class MetadataScheme(str, Enum):
    FOOOCUS = 'fooocus'
    A1111 = 'a1111'


# =============================================================================
# Refiner Swap Method
# =============================================================================
class RefinerSwapMethod(str, Enum):
    JOINT = 'joint'
    SWAP = 'swap'
    ALTERNATIVE = 'alternative'
