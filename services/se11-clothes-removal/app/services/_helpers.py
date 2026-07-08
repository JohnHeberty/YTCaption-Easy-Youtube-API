"""Shared helper functions for SE11 Clothes Removal pipelines.

Refactored into focused modules:
- config_loader.py: NSFWConfig, ClothesConfig, ScoringWeights, YAML loading
- image_utils.py: Base64, decode, encode, mask helpers
- scoring.py: Composite scoring, skin detection
- detection_fallbacks.py: Person detection with fallback strategies
- se8_postprocess.py: SE8 upscale and face restore helpers
"""
from __future__ import annotations

# Re-export all public API for backward compatibility
from .config_loader import (
    NSFWConfig,
    ClothesConfig,
    ScoringWeights,
    DEFAULT_BASE_MODEL,
    DEFAULT_CLOTHES_NEGATIVE,
    NSFW_PROMPT,
    NSFW_NEGATIVE,
    LORAS_CLOTHES,
    CLOTHES_CLASSES,
    SCORING,
    get_nsfw_config,
    get_clothes_config,
    _make_lora,
    _load_nsfw_config,
    _load_clothes_config,
    _build_scoring_from_config,
    _HARDCODED_DEFAULTS,
    _CLOTHES_DEFAULTS,
    _CONFIGS_DIR,
)
from .image_utils import (
    decode_image,
    to_data_uri,
    strip_data_uri,
    fix_b64_padding,
    combine_masks,
)
from .scoring import (
    detect_skin_hsv,
    compute_composite_score,
)
from .detection_fallbacks import (
    detect_person_with_fallbacks,
    _grabcut_fallback,
    _face_ellipse_fallback,
)
from .se8_postprocess import (
    upscale_result,
    restore_face,
)

__all__ = [
    "NSFWConfig",
    "ClothesConfig",
    "ScoringWeights",
    "DEFAULT_BASE_MODEL",
    "DEFAULT_CLOTHES_NEGATIVE",
    "NSFW_PROMPT",
    "NSFW_NEGATIVE",
    "LORAS_CLOTHES",
    "CLOTHES_CLASSES",
    "SCORING",
    "get_nsfw_config",
    "get_clothes_config",
    "_make_lora",
    "_load_nsfw_config",
    "_load_clothes_config",
    "_build_scoring_from_config",
    "_HARDCODED_DEFAULTS",
    "_CLOTHES_DEFAULTS",
    "_CONFIGS_DIR",
    "decode_image",
    "to_data_uri",
    "strip_data_uri",
    "fix_b64_padding",
    "combine_masks",
    "detect_skin_hsv",
    "compute_composite_score",
    "detect_person_with_fallbacks",
    "_grabcut_fallback",
    "_face_ellipse_fallback",
    "upscale_result",
    "restore_face",
]
