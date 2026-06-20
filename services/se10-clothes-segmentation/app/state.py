"""Shared application state for SE10 Clothes Segmentation."""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.services.segmentor import ClothesSegmentor

_segmentor: Optional["ClothesSegmentor"] = None


def get_segmentor(segmentor: Optional["ClothesSegmentor"] = None) -> Optional["ClothesSegmentor"]:
    """Return the loaded segmentor instance.

    Args:
        segmentor: Optional override for DI/testing. If provided, sets the
                   global instance and returns it.
    """
    global _segmentor
    if segmentor is not None:
        _segmentor = segmentor
    return _segmentor


def set_segmentor(segmentor: "ClothesSegmentor") -> None:
    """Set the segmentor instance (called during startup)."""
    global _segmentor
    _segmentor = segmentor


def clear_segmentor() -> None:
    """Clear the segmentor instance (called during shutdown)."""
    global _segmentor
    _segmentor = None
