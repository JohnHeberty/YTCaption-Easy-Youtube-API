"""
CLIP-based zero-shot subtitle classifier.

Sprint 06 - Ensemble Setup
Uses OpenAI's CLIP model for zero-shot classification of video frames.
"""

import torch
import cv2
import numpy as np
from typing import Dict, List
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

from .base_detector import BaseSubtitleDetector


class CLIPClassifier(BaseSubtitleDetector):
    """
    Zero-shot subtitle classifier using CLIP (OpenAI).
    
    Classifies video frames as "with subtitles" or "without subtitles"
    using natural language prompts. No training required.
    
    Model: openai/clip-vit-base-patch32
    Training data: 400M image-text pairs
    
    Attributes:
        model: CLIP model for image-text matching
        processor: CLIP processor for image/text preprocessing
        device: Computing device ('cuda' or 'cpu')
        prompts: Text prompts for classification
    """
    
    def __init__(self, device: str = None, n_frames: int = 6):
        """
        Initialize CLIP classifier.
        
        Args:
            device: Computing device ('cuda', 'cpu', or None for auto)
            n_frames: Number of frames to extract from video
        """
        super().__init__()
        
        # Auto-detect device
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        self.device = device
        self.n_frames = n_frames
        
        # Load CLIP model (cached after first download)
        print(f"[CLIP] Loading model on {self.device}...")
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(self.device)
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        
        # Zero-shot prompts
        self.prompts = [
            "A video frame with burned-in subtitles at the bottom",
            "A video frame with hardcoded text captions or subtitles",
            "A clean video frame without any subtitles or text overlays",
            "A video frame with no embedded captions or text"
        ]
        
        print(f"[CLIP] Model loaded successfully")
    
    def detect(self, video_path: str) -> Dict:
        """
        Detect subtitles using CLIP zero-shot classification.
        
        Args:
            video_path: Path to video file
        
        Returns:
            {
                'has_subtitles': bool,
                'confidence': float (0-1),
                'metadata': {
                    'frame_results': list,    # Per-frame results
                    'votes': str,              # E.g., "4/6"
                    'model': 'clip',           # Model identifier
                    'device': str              # 'cuda' or 'cpu'
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
                    'model': 'clip'
                }
            }
        
        # Classify each frame
        frame_results = []
        for i, frame in enumerate(frames):
            result = self._classify_frame(frame)
            frame_results.append(result)
        
        # Aggregate results (majority voting across frames)
        has_subtitles_votes = sum(1 for r in frame_results if r['has_subtitles'])
        total_frames = len(frame_results)
        
        # Decision: majority of frames must detect subtitles
        has_subtitles = has_subtitles_votes >= (total_frames / 2)
        
        # Confidence: average confidence across all frames
        confidence_scores = [r['confidence'] for r in frame_results]
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        return {
            'has_subtitles': has_subtitles,
            'confidence': avg_confidence,
            'metadata': {
                'frame_results': frame_results,
                'votes': f'{has_subtitles_votes}/{total_frames}',
                'model': 'clip',
                'device': self.device
            }
        }
    
    def _classify_frame(self, frame: np.ndarray) -> Dict:
        """
        Classify a single frame using CLIP.
        
        Args:
            frame: Frame as numpy array (BGR format from OpenCV)
        
        Returns:
            {
                'has_subtitles': bool,
                'confidence': float
            }
        """
        # Convert BGR (OpenCV) to RGB (PIL)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        
        # Process with CLIP
        inputs = self.processor(
            text=self.prompts,
            images=pil_image,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        # Get predictions
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits_per_image  # Shape: [1, 4]
            probs = logits.softmax(dim=1)       # Normalize probabilities
        
        # Aggregate probabilities
        # Prompts 0-1: "with subtitles"
        # Prompts 2-3: "without subtitles"
        has_subtitles_prob = (probs[0][0] + probs[0][1]) / 2
        no_subtitles_prob = (probs[0][2] + probs[0][3]) / 2
        
        # Decision
        has_subtitles = has_subtitles_prob > no_subtitles_prob
        confidence = max(has_subtitles_prob, no_subtitles_prob).item()
        
        return {
            'has_subtitles': has_subtitles,
            'confidence': confidence
        }
    
    def _extract_frames(self, video_path: str, n_frames: int = 6) -> List[np.ndarray]:
        """
        Extract frames from video at evenly distributed timestamps.
        
        Uses same strategy as Sprint 01 (temporal sampling).
        
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
        # Avoid very start/end (often has different content)
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
            'clip' (for ensemble voting)
        """
        return 'clip'
    
    def _get_default_weight(self) -> float:
        """
        Get default voting weight.
        
        Returns:
            0.30 (30% - second highest weight)
            
        Rationale:
            - Strong zero-shot capabilities
            - Trained on 400M image-text pairs
            - Good generalization to unseen data
            - Slightly less weight than Paddle (which is domain-optimized)
        """
        return 0.30
