"""Shared application state for SE10 Clothes Segmentation."""
from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.segmentor import ClothesSegmentor

_segmentor: ClothesSegmentor | None = None
_idle_timer: threading.Timer | None = None
_IDLE_CHECK_INTERVAL = 30  # seconds between idle checks


def get_segmentor(segmentor: ClothesSegmentor | None = None) -> ClothesSegmentor | None:
    """Return the loaded segmentor instance.

    Args:
        segmentor: Optional override for DI/testing. If provided, sets the
                   global instance and returns it.
    """
    global _segmentor
    if segmentor is not None:
        _segmentor = segmentor
    return _segmentor


def set_segmentor(segmentor: ClothesSegmentor) -> None:
    """Set the segmentor instance (called during startup)."""
    global _segmentor
    _segmentor = segmentor
    _start_idle_checker()


def clear_segmentor() -> None:
    """Clear the segmentor instance (called during shutdown)."""
    global _segmentor, _idle_timer
    if _idle_timer is not None:
        _idle_timer.cancel()
        _idle_timer = None
    _segmentor = None


def _idle_check_loop() -> None:
    """Background loop that checks for idle timeout and unloads models."""
    global _idle_timer
    try:
        if _segmentor is not None:
            _segmentor._check_idle_unload()
    except Exception:
        pass
    # Schedule next check
    _idle_timer = threading.Timer(_IDLE_CHECK_INTERVAL, _idle_check_loop)
    _idle_timer.daemon = True
    _idle_timer.start()


def _start_idle_checker() -> None:
    """Start the background idle checker timer."""
    global _idle_timer
    if _idle_timer is not None:
        _idle_timer.cancel()
    _idle_timer = threading.Timer(_IDLE_CHECK_INTERVAL, _idle_check_loop)
    _idle_timer.daemon = True
    _idle_timer.start()
