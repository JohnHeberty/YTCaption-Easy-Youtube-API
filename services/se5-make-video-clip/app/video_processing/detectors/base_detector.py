"""
Base detector interface for subtitle detection.

Sprint 06 - Ensemble Setup
All subtitle detectors must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Dict


class BaseSubtitleDetector(ABC):
    """
    Abstract base class for subtitle detectors.
    
    All detectors in the ensemble must implement this interface
    to ensure consistent API and enable proper voting/aggregation.
    """
    
    def __init__(self):
        """Initialize base detector with custom weight support."""
        self._custom_weight = None  # Can be overridden by ensemble
    
    @abstractmethod
    def detect(self, video_path: str) -> Dict:
        """
        Detect subtitles in a video.
        
        Args:
            video_path: Absolute path to the video file
        
        Returns:
            Dictionary with keys:
                - has_subtitles: bool - Whether subtitles were detected
                - confidence: float - Confidence score (0-1)
                - metadata: dict - Additional detector-specific information
        
        Raises:
            FileNotFoundError: If video file doesn't exist
            ValueError: If video is invalid/corrupted
        """
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """
        Get the name/identifier of this detector.
        
        Returns:
            String identifier (e.g., 'paddle', 'clip', 'easyocr')
        """
        pass
    
    @abstractmethod
    def _get_default_weight(self) -> float:
        """
        Get the default voting weight for this detector.
        
        Subclasses should implement this to return their default weight.
        
        Returns:
            Weight value between 0 and 1.
        """
        pass
    
    def get_weight(self) -> float:
        """
        Get the voting weight for this detector.
        
        Returns custom weight if set, otherwise returns default weight.
        
        Returns:
            Weight value between 0 and 1.
            Higher weight = more influence in ensemble voting.
        """
        if self._custom_weight is not None:
            return self._custom_weight
        return self._get_default_weight()
    
    def set_weight(self, weight: float) -> None:
        """
        Set a custom weight for this detector.
        
        Args:
            weight: Weight value between 0 and 1
        
        Raises:
            ValueError: If weight is not in [0, 1]
        """
        if not (0 <= weight <= 1):
            raise ValueError(f"Weight must be in [0, 1], got {weight}")
        self._custom_weight = weight
    
    def validate_video_path(self, video_path: str) -> None:
        """
        Validate that video file exists and is accessible.
        
        Args:
            video_path: Path to video file
        
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        import os
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        if not os.path.isfile(video_path):
            raise ValueError(f"Path is not a file: {video_path}")
