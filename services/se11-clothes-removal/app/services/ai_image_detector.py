"""AI Image Detection — blocks real person photos from NSFW pipeline.

Uses Bombek1/ai-image-detector-siglip-dinov2 (99.1% AUC) to detect whether
an image is AI-generated or a real photograph. Real photos are rejected with
HTTP 400 before any processing occurs.
"""
from __future__ import annotations

import io
from typing import Any

from common.log_utils import get_logger

logger = get_logger(__name__)

# Singleton state
_model: Any = None
_transform: Any = None
_loading = False


def _load_model() -> None:
    """Lazy-load the AI image detector model on first call."""
    global _model, _transform, _loading

    if _model is not None or _loading:
        return

    _loading = True
    try:
        import torch
        import timm
        from timm.data import resolve_data_config
        from timm.data.transforms_factory import create_transform

        logger.info("Loading AI image detector model (first call, ~10-20s)...")
        model = timm.create_model(
            "hf_hub:RomBombom/ai-image-detector-siglip-dinov2",
            pretrained=True,
        )
        model.eval()

        if torch.cuda.is_available():
            model = model.cuda()

        data_config = resolve_data_config(model.pretrained_cfg)
        transform = create_transform(**data_config)

        _model = model
        _transform = transform
        logger.info("AI image detector loaded successfully")
    except Exception as exc:
        logger.error("Failed to load AI image detector: %s", exc)
        _model = None
        _transform = None
    finally:
        _loading = False


def check_image_is_ai_generated(image_bytes: bytes) -> tuple[bool, float]:
    """Check whether an image is AI-generated.

    Args:
        image_bytes: Raw image file bytes (PNG/JPEG/WebP).

    Returns:
        Tuple of (is_ai_generated: bool, confidence: float).
        is_ai_generated=True means the image is AI-generated (OK for NSFW).
        is_ai_generated=False means it's likely a real photo (REJECT).
    """
    _load_model()

    if _model is None or _transform is None:
        logger.warning("AI detector unavailable — allowing image by default")
        return True, 0.0

    try:
        import torch
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        tensor = _transform(img).unsqueeze(0)

        if torch.cuda.is_available():
            tensor = tensor.cuda()

        with torch.no_grad():
            output = _model(tensor)
            probs = torch.softmax(output, dim=1)
            # Class 0 = AI-generated, Class 1 = Real (per model card)
            ai_prob = probs[0][0].item()

        is_ai = ai_prob >= 0.5
        logger.info(
            "AI image detection: ai_prob=%.4f, is_ai=%s",
            ai_prob,
            is_ai,
        )
        return is_ai, ai_prob

    except Exception as exc:
        logger.error("AI image detection failed: %s — allowing by default", exc)
        return True, 0.0
