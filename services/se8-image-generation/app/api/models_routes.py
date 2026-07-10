"""Engine/model routes for SE8 Image Engine.

Provides model listing, styles, and VRAM cleanup.
"""

from __future__ import annotations
from common.log_utils import get_logger

from fastapi import APIRouter

from app.api.schemas import (
    AllModelNamesResponse,
    ErrorResponse,
    ProcessRestartResponse,
    StyleDetail,
    VRAMCleanupResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/engines", tags=["Engines"])


@router.get("/all-models", response_model=AllModelNamesResponse)
def get_all_models() -> AllModelNamesResponse:
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


@router.get("/styles", response_model=list[str])
def get_styles() -> list[str]:
    """Get all legal style presets."""
    try:
        from modules.sdxl_styles import legal_style_names

        return legal_style_names
    except ImportError:
        logger.warning("Required modules not available, returning empty styles list")
        return []


@router.get("/styles-detail", response_model=list[StyleDetail])
def get_styles_detail() -> list[StyleDetail]:
    """Get all styles with their prompt templates."""
    try:
        from modules.sdxl_styles import legal_style_names, styles

        result: list[StyleDetail] = []
        for name in legal_style_names:
            p, n = styles.get(name, ("", ""))
            result.append(
                StyleDetail(name=name, prompt=p, negative_prompt=n)
            )
        return result
    except ImportError:
        logger.warning("Required modules not available, returning empty styles-detail")
        return []


@router.get(
    "/clean_vram",
    response_model=VRAMCleanupResponse,
    responses={500: {"model": ErrorResponse}},
)
def clean_vram() -> VRAMCleanupResponse:
    """Unload all models and clean VRAM."""
    try:
        from app.services.model_manager import get_model_manager

        mm = get_model_manager()
        mm.cleanup_models()
        mm.unload_all()
        return VRAMCleanupResponse(message="ok")
    except Exception as e:
        logger.error("Failed to clean VRAM: %s", e)
        return VRAMCleanupResponse(message="error", detail=str(e))


@router.get(
    "/cleanup",
    response_model=ProcessRestartResponse,
    responses={500: {"model": ErrorResponse}},
)
def cleanup_memory() -> ProcessRestartResponse:
    """Full memory cleanup — releases GPU VRAM, unloads models, then restarts process.

    PyTorch C++ allocator retains mmap'd anonymous pages after model unload.
    gc.collect/malloc_trim cannot reclaim them — only process replacement (os.execv)
    forces the kernel to munmap all pages. Server restarts in ~2s.
    """
    import gc

    import psutil
    proc = psutil.Process()
    rss_before = proc.memory_info().rss / 1024**3

    try:
        from app.services.model_manager import get_model_manager
        from app.services.pipeline import get_pipeline

        pipeline = get_pipeline()
        mm = get_model_manager()

        pipeline.clear_caches()
        mm.cleanup_models()
        mm.unload_all()
        gc.collect()
    except Exception as e:
        logger.error("Cleanup pre-restart failed: %s", e)

    rss_after_cleanup = proc.memory_info().rss / 1024**3

    import os
    import sys
    import threading

    def _restart() -> None:
        import time
        time.sleep(1.0)
        os.execv(sys.executable, ["python3.11", "-m", "uvicorn", "app.main:app",
                                   "--host", "0.0.0.0", "--port", "8008"])

    threading.Thread(target=_restart, daemon=True).start()

    return ProcessRestartResponse(
        message="Server restarting to free all memory",
        rss_before_gb=round(rss_before, 2),
        rss_after_cleanup_gb=round(rss_after_cleanup, 2),
    )
