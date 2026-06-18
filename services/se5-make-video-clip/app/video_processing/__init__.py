"""
Video Processing module - Frame extraction, OCR, validation

Components for video analysis and validation.
"""

from .frame_extractor import FFmpegFrameExtractor, ExtractionResult
from .ocr_detector import OCRDetector
from .video_validator import VideoValidator

__all__ = [
    'FrameExtractor',
    'OCRDetector',
    'VideoValidator',
]
