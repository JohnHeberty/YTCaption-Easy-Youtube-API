"""
EasyOCR detector for ensemble.

Sprint 06 - Ensemble Setup
Alternative OCR detector using EasyOCR engine (supports 80+ languages).
"""

import cv2
import numpy as np
from typing import Dict, List
import easyocr

from .base_detector import BaseSubtitleDetector


class EasyOCRDetector(BaseSubtitleDetector):
    """
    Subtitle detector using EasyOCR.
    
    Alternative to PaddleOCR, provides:
    - Support for 80+ languages
    - Different OCR engine (CRAFT + CRNN)
    - Redundancy in ensemble
    
    Attributes:
        reader: EasyOCR Reader instance
        languages: List of language codes to detect
        gpu: Whether to use GPU acceleration
    """
    
    def __init__(self, languages: List[str] = None, gpu: bool = True, n_frames: int = 6):
        """
        Initialize EasyOCR detector.
        
        Args:
            languages: List of language codes (e.g., ['en', 'pt', 'es'])
                      Default: ['en'] (English only for speed)
            gpu: Whether to use GPU (if available)
            n_frames: Number of frames to extract from video
        """
        super().__init__()
        
        if languages is None:
            languages = ['en']  # English only by default (faster)
        
        self.languages = languages
        self.gpu = gpu
        self.n_frames = n_frames
        
        print(f"[EasyOCR] Loading model for languages: {languages} (GPU: {gpu})...")
        self.reader = easyocr.Reader(languages, gpu=self.gpu)
        print(f"[EasyOCR] Model loaded successfully")
    
    def detect(self, video_path: str) -> Dict:
        """
        Detect subtitles using EasyOCR.
        
        Args:
            video_path: Path to video file
        
        Returns:
            {
                'has_subtitles': bool,
                'confidence': float (0-1),
                'metadata': {
                    'frame_results': list,    # Per-frame results
                    'text': str,               # Detected text
                    'votes': str,              # E.g., "4/6"
                    'model': 'easyocr',        # Model identifier
                    'languages': list          # Detected languages
                }
            }
        """
        self.validate_video_path(video_path)
        
        # Extract frames from video
        frames = self._extract_frames(video_path, n_frames=self.n_frames)
        
        if not frames:
            return {
                'has_subtitles': False,
                'confidence': 0.0,
                'metadata': {
                    'error': 'Could not extract frames from video',
                    'model': 'easyocr'
                }
            }
        
        # Detect text in each frame
        frame_results = []
        all_texts = []
        
        for i, frame in enumerate(frames):
            result = self._detect_in_frame(frame)
            frame_results.append(result)
            
            if result['has_subtitles']:
                all_texts.append(result.get('text', ''))
        
        # Aggregate results (majority voting across frames)
        has_subtitles_votes = sum(1 for r in frame_results if r['has_subtitles'])
        total_frames = len(frame_results)
        
        # Decision: majority of frames must detect subtitles
        has_subtitles = has_subtitles_votes >= (total_frames / 2)
        
        # Confidence: average confidence across all frames
        confidence_scores = [r['confidence'] for r in frame_results]
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        # Combine all detected texts
        combined_text = ' '.join(all_texts) if all_texts else ''
        
        return {
            'has_subtitles': has_subtitles,
            'confidence': avg_confidence,
            'metadata': {
                'frame_results': frame_results,
                'text': combined_text,
                'votes': f'{has_subtitles_votes}/{total_frames}',
                'model': 'easyocr',
                'languages': self.languages
            }
        }
    
    def _detect_in_frame(self, frame: np.ndarray) -> Dict:
        """
        Detect text in a single frame using EasyOCR.
        
        Args:
            frame: Frame as numpy array (BGR format from OpenCV)
        
        Returns:
            {
                'has_subtitles': bool,
                'confidence': float,
                'text': str (optional)
            }
        """
        frame_height, frame_width = frame.shape[:2]
        
        # Crop to bottom 30% (where subtitles typically are)
        # This speeds up OCR and reduces false positives
        bottom_start = int(frame_height * 0.70)
        bottom_region = frame[bottom_start:, :, :]
        
        # Convert BGR to RGB (EasyOCR expects RGB)
        bottom_rgb = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2RGB)
        
        # Detect text
        try:
            results = self.reader.readtext(bottom_rgb)
        except Exception as e:
            print(f"[EasyOCR] Error detecting text: {e}")
            return {
                'has_subtitles': False,
                'confidence': 0.0
            }
        
        if not results:
            return {
                'has_subtitles': False,
                'confidence': 0.0
            }
        
        # Analyze detections
        # EasyOCR result format: [(bbox, text, confidence), ...]
        bottom_texts = []
        confidences = []
        
        for (bbox, text, conf) in results:
            # bbox is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            # Get y-coordinate (check if in bottom region)
            y_coords = [point[1] for point in bbox]
            avg_y = sum(y_coords) / len(y_coords)
            
            # Consider text in bottom 50% of the cropped region
            if avg_y > (bottom_region.shape[0] * 0.50):
                bottom_texts.append(text)
                confidences.append(conf)
        
        if not bottom_texts:
            return {
                'has_subtitles': False,
                'confidence': 0.0
            }
        
        # Calculate overall confidence
        avg_confidence = sum(confidences) / len(confidences)
        combined_text = ' '.join(bottom_texts)
        
        # Decision criteria:
        # 1. At least 1 text detected in bottom region
        # 2. Average confidence >= 0.5
        # 3. Combined text length >= 3 characters (avoid single letters)
        has_subtitles = (
            len(bottom_texts) >= 1 and
            avg_confidence >= 0.5 and
            len(combined_text.strip()) >= 3
        )
        
        return {
            'has_subtitles': has_subtitles,
            'confidence': avg_confidence,
            'text': combined_text
        }
    
    def _extract_frames(self, video_path: str, n_frames: int = 6) -> List[np.ndarray]:
        """
        Extract frames from video at evenly distributed timestamps.
        
        Uses same strategy as CLIP classifier.
        
        Args:
            video_path: Path to video file
            n_frames: Number of frames to extract
        
        Returns:
            List of frames as numpy arrays
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            return []
        
        # Get video properties
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        if fps <= 0 or total_frames <= 0:
            cap.release()
            return []
        
        duration = total_frames / fps
        
        # Calculate timestamps (20%-95% of video duration)
        timestamps = []
        for i in range(n_frames):
            ratio = 0.2 + (i / (n_frames - 1)) * 0.75  # 0.2 to 0.95
            ts = duration * ratio
            timestamps.append(ts)
        
        # Extract frames
        frames = []
        for ts in timestamps:
            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
            ret, frame = cap.read()
            
            if ret and frame is not None:
                frames.append(frame)
        
        cap.release()
        
        return frames
    
    def get_model_name(self) -> str:
        """
        Get model identifier.
        
        Returns:
            'easyocr' (for ensemble voting)
        """
        return 'easyocr'
    
    def _get_default_weight(self) -> float:
        """
        Get default voting weight.
        
        Returns:
            0.25 (25% - third weight)
            
        Rationale:
            - Alternative OCR engine (redundancy)
            - Good multi-language support
            - Less weight than Paddle (which is domain-optimized)
            - Provides diversity in ensemble
        """
        return 0.25
