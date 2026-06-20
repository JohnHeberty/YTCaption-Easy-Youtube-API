"""Domain constants for clothes segmentation service."""
from __future__ import annotations

from enum import Enum


class ClothingClass(str, Enum):
    """Clothing classes detected by GroundingDINO."""
    HAT = "hat"
    SUNGLASSES = "sunglasses"
    SHIRT = "shirt"
    BLOUSE = "blouse"
    JACKET = "jacket"
    SWEATER = "sweater"
    BLAZER = "blazer"
    CARDIGAN = "cardigan"
    HANDBAG = "handbag"
    SKIRT = "skirt"
    PANTS = "pants"
    DRESS = "dress"
    SHOES = "shoes"
    BOOTS = "boots"
    SLIPPERS = "slippers"


CLOTHING_CLASSES: list[str] = [c.value for c in ClothingClass]

DEFAULT_BOX_THRESHOLD: float = 0.10
DEFAULT_TEXT_THRESHOLD: float = 0.10
DEFAULT_MAX_AREA_PCT: float = 0.29
DEFAULT_MAX_OBJECTS: int = 50

ALLOWED_EXTENSIONS: tuple[str, ...] = (".jpg", ".jpeg", ".png")
MAX_FILE_SIZE_MB: int = 20

CHECKPOINT_GROUNDINGDINO: str = "groundingdino_swint_ogc.pth"
CHECKPOINT_SAM2_TINY: str = "sam2_hiera_tiny.pt"

GD_CONFIG_SwinT: str = "groundingdino/config/GroundingDINO_SwinT_OGC.py"
SAM2_CONFIG_TINY: str = "configs/sam2/sam2_hiera_t.yaml"
