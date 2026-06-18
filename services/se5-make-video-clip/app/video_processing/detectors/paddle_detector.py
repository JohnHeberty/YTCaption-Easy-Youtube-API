"""
PaddleOCR detector wrapper for ensemble.

Sprint 06 - Ensemble Setup
Wraps the existing SubtitleDetectorV2 (Sprint 00-04) into the ensemble interface.
"""

from typing import Dict
from .base_detector import BaseSubtitleDetector
from ..subtitle_detector_v2 import SubtitleDetectorV2


class PaddleDetector(BaseSubtitleDetector):
    """
    Wrapper for PaddleOCR-based SubtitleDetectorV2.
    
    Integrates Sprint 00-04 implementation (baseline + multi-ROI)
    into the ensemble system.
    
    Attributes:
        detector: SubtitleDetectorV2 instance with multi-ROI support
        roi_mode: ROI detection mode ('bottom', 'multi', 'all')
    """
    
    def __init__(self, roi_mode: str = 'multi'):
        """
        Initialize Paddle detector wrapper.
        
        Args:
            roi_mode: Detection mode
                - 'bottom': Only bottom 25% (Sprint 00-02 compatible)
                - 'multi': Multi-ROI with fallback (Sprint 04, recommended)
                - 'all': Try all ROIs without early exit (debug mode)
        """
        super().__init__()
        self.roi_mode = roi_mode
        self.detector = SubtitleDetectorV2(roi_mode=roi_mode)
    
    def detect(self, video_path: str) -> Dict:
        """
        Detect subtitles using PaddleOCR + Multi-ROI.
        
        Args:
            video_path: Path to video file
        
        Returns:
            {
                'has_subtitles': bool,
                'confidence': float (0-1),
                'metadata': {
                    'text': str,              # Detected text
                    'roi_used': str,          # ROI that found text ('bottom', 'top', etc.)
                    'model': 'paddleocr',     # Model identifier
                    'roi_mode': str,          # Detection mode used
                    'detections': list        # Raw OCR detections (optional)
                }
            }
        """
        self.validate_video_path(video_path)
        
        # Call existing SubtitleDetectorV2
        has_subs, confidence, text, metadata = self.detector.detect_in_video_with_multi_roi(video_path)
        
        return {
            'has_subtitles': has_subs,
            'confidence': confidence,
            'metadata': {
                'text': text,
                'roi_used': metadata.get('roi_used', 'unknown'),
                'model': 'paddleocr',
                'roi_mode': self.roi_mode,
                'multi_roi_available': self.roi_mode == 'multi'
            }
        }
    
    def get_model_name(self) -> str:
        """
        Get model identifier.
        
        Returns:
            'paddle' (for ensemble voting)
        """
        return 'paddle'
    
    def _get_default_weight(self) -> float:
        """
        Get default voting weight.
        
        Returns:
            0.35 (35% - highest weight in ensemble)
            
        Rationale:
            - Most reliable (100% accuracy in Sprint 00-04)
            - Optimized with multi-ROI fallback
            - Primary detector in ensemble
        """
        return 0.35
