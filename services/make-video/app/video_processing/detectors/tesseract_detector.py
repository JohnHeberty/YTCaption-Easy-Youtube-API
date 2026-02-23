"""
Tesseract OCR detector for subtitle detection.

Sprint 06/07 - Alternative detector to replace low-performing CLIP.
Uses pytesseract for OCR-based subtitle detection.
"""

import cv2
import numpy as np
import pytesseract
from typing import Dict, List
from PIL import Image

from .base_detector import BaseSubtitleDetector


class TesseractDetector(BaseSubtitleDetector):
    """
    Tesseract OCR-based subtitle detector.
    
    Detects subtitles by running OCR on video frames and counting
    frames with text in subtitle regions.
    
    Attributes:
        n_frames: Number of frames to sample
        roi_height: Height percentage for subtitle region (e.g., 0.3 = bottom 30%)
        min_text_length: Minimum text length to consider valid
        detection_threshold: Minimum ratio of frames with text
    """
    
    def __init__(
        self,
        n_frames: int = 6,
        roi_height: float = 0.3,
        min_text_length: int = 10,
        detection_threshold: float = 0.5
    ):
        """
        Initialize Tesseract detector.
        
        Args:
            n_frames: Number of frames to extract
            roi_height: ROI height as percentage (0.3 = bottom 30%)
            min_text_length: Minimum characters to consider valid text
            detection_threshold: Minimum ratio of frames with text (0-1)
        """
        super().__init__()
        self.n_frames = n_frames
        self.roi_height = roi_height
        self.min_text_length = min_text_length
        self.detection_threshold = detection_threshold
        
        # Tesseract config optimized for subtitles
        self.tesseract_config = '--psm 6 --oem 3'  # Uniform block of text, LSTM mode
    
    def detect(self, video_path: str) -> Dict:
        """
        Detect subtitles using Tesseract OCR.
        
        Args:
            video_path: Path to video file
        
        Returns:
            {
                'has_subtitles': bool,
                'confidence': float (0-1),
                'metadata': {
                    'frames_with_text': int,
                    'total_frames': int,
                    'text_samples': list,   # First 3 detected texts
                    'model': 'tesseract',
                    'version': str          # Tesseract version
                }
            }
        """
        self.validate_video_path(video_path)
        
        # Extract frames
        frames = self._extract_frames(video_path, n_frames=self.n_frames)
        
        if not frames:
            return {
                'has_subtitles': False,
                'confidence': 0.0,
                'metadata': {
                    'error': 'Could not extract frames from video',
                    'model': 'tesseract'
                }
            }
        
        # Process each frame
        frames_with_text = 0
        text_samples = []
        
        for frame in frames:
            # Extract subtitle region (bottom portion)
            roi = self._extract_roi(frame)
            
            # Apply preprocessing
            processed = self._preprocess_frame(roi)
            
            # Run OCR
            text = pytesseract.image_to_string(
                processed,
                config=self.tesseract_config
            ).strip()
            
            # Count if valid text found
            if len(text) >= self.min_text_length:
                frames_with_text += 1
                if len(text_samples) < 3:  # Keep first 3 samples
                    text_samples.append(text[:50])  # Truncate to 50 chars
        
        # Calculate metrics
        total_frames = len(frames)
        ratio = frames_with_text / total_frames if total_frames > 0 else 0.0
        
        # Decision
        has_subtitles = ratio >= self.detection_threshold
        confidence = ratio
        
        return {
            'has_subtitles': has_subtitles,
            'confidence': confidence,
            'metadata': {
                'frames_with_text': frames_with_text,
                'total_frames': total_frames,
                'text_samples': text_samples,
                'model': 'tesseract',
                'version': pytesseract.get_tesseract_version()
            }
        }
    
    def _extract_roi(self, frame: np.ndarray) -> np.ndarray:
        """
        Extract subtitle region from frame.
        
        Args:
            frame: Input frame (BGR format)
        
        Returns:
            ROI region (bottom portion of frame)
        """
        height = frame.shape[0]
        roi_start = int(height * (1 - self.roi_height))
        return frame[roi_start:, :]
    
    def _preprocess_frame(self, frame: np.ndarray) -> Image.Image:
        """
        Preprocess frame for better OCR recognition.
        
        Applies:
        - Grayscale conversion
        - Contrast enhancement (CLAHE)
        - Binarization (Otsu's method)
        
        Args:
            frame: Input frame (BGR format)
        
        Returns:
            Preprocessed PIL Image
        """
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply CLAHE (contrast enhancement)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Apply binary thresholding (Otsu's method)
        _, binary = cv2.threshold(
            enhanced, 0, 255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        
        # Convert to PIL Image
        return Image.fromarray(binary)
    
    def _extract_frames(self, video_path: str, n_frames: int = 6) -> List[np.ndarray]:
        """
        Extract frames from video at evenly distributed timestamps.
        
        Args:
            video_path: Path to video file
            n_frames: Number of frames to extract
        
        Returns:
            List of frames as numpy arrays (BGR format)
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            return []
        
        # Get video properties
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if total_frames < n_frames:
            n_frames = total_frames
        
        # Calculate frame indices (evenly distributed)
        indices = np.linspace(0, total_frames - 1, n_frames, dtype=int)
        
        frames = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                frames.append(frame)
        
        cap.release()
        return frames
    
    def get_model_name(self) -> str:
        """
        Get model identifier.
        
        Returns:
            Model name string
        """
        return "tesseract"
    
    def _get_default_weight(self) -> float:
        """
        Get default weight for ensemble voting.
        
        Returns:
            Default weight (1.0 for equal weight)
        """
        return 1.0
