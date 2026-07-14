from __future__ import annotations

"""
OCR Detection Module — Legacy Shim

DEPRECATED: This module is a backward-compatibility shim.
All classes are re-exported from ocr_detector_advanced.py (PaddleOCR).
"""

from .ocr_detector_advanced import (
    OCRResult,
    PaddleOCRDetector as OCRDetector,
    get_ocr_detector,
)

__all__ = ['OCRResult', 'OCRDetector', 'get_ocr_detector']
