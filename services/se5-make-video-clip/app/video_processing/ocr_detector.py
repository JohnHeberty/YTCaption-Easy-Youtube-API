from __future__ import annotations

"""
OCR Detector - Backward Compatibility Wrapper

Wrapper para manter compatibilidade com código antigo
Redireciona para PaddleOCR detector
"""

from .ocr_detector_advanced import (
    get_ocr_detector,
    PaddleOCRDetector as OCRDetector,
    OCRResult
)

__all__ = ['get_ocr_detector', 'OCRDetector', 'OCRResult']
