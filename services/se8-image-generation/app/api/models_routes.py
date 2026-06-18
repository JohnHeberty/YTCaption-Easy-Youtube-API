"""Engine/model routes for SE8 Image Engine.

Provides model listing, styles, and VRAM cleanup.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter

from app.domain.models import AllModelNamesResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/engines", tags=["Engines"])


@router.get("/all-models", response_model=AllModelNamesResponse)
def get_all_models():
    """Get all filenames of base models and LoRAs."""
    try:
        from modules import config

        config.update_files()
        return AllModelNamesResponse(
            model_filenames=config.model_filenames,
            lora_filenames=config.lora_filenames,
        )
    except ImportError:
        logger.warning("Required modules not available, returning empty model list")
        return AllModelNamesResponse(model_filenames=[], lora_filenames=[])


@router.get("/styles", response_model=List[str])
def get_styles():
    """Get all legal style presets."""
    try:
        from modules.sdxl_styles import legal_style_names

        return legal_style_names
    except ImportError:
        logger.warning("Required modules not available, returning empty styles list")
        return []


@router.get("/styles-detail")
def get_styles_detail():
    """Get all styles with their prompt templates."""
    try:
        from modules.sdxl_styles import legal_style_names, styles

        result = []
        for name in legal_style_names:
            p, n = styles.get(name, ("", ""))
            result.append(
                {
                    "name": name,
                    "prompt": p,
                    "negative_prompt": n,
                }
            )
        return result
    except ImportError:
        logger.warning("Required modules not available, returning empty styles-detail")
        return []


@router.get("/clean_vram")
def clean_vram():
    """Unload all models and clean VRAM."""
    try:
        from app.services.model_manager import get_model_manager

        mm = get_model_manager()
        mm.cleanup_models()
        mm.unload_all()
        return {"message": "ok"}
    except Exception as e:
        logger.error("Failed to clean VRAM: %s", e)
        return {"message": "error", "detail": str(e)}
