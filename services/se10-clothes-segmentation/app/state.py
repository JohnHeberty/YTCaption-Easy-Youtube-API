"""Shared application state for SE10 Clothes Segmentation."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.segmentor import ClothesSegmentor

_segmentor: ClothesSegmentor | None = None


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


def clear_segmentor() -> None:
    """Clear the segmentor instance (called during shutdown)."""
    global _segmentor
    _segmentor = None
