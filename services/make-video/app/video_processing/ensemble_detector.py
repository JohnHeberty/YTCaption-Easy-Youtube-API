"""
Ensemble detector that combines multiple subtitle detectors.

Sprint 06 - Ensemble Setup
Combines PaddleOCR, CLIP, and EasyOCR with weighted voting for robust detection.
"""

from typing import Dict, List, Optional
import time

from .detectors.base_detector import BaseSubtitleDetector
from .detectors.paddle_detector import PaddleDetector
from .detectors.clip_classifier import CLIPClassifier
from .detectors.easyocr_detector import EasyOCRDetector


class EnsembleSubtitleDetector:
    """
    Ensemble of multiple subtitle detectors with weighted voting.
    
    Combines predictions from multiple models to achieve higher
    accuracy and robustness than any single detector.
    
    Default detectors:
        - PaddleOCR (35% weight): Domain-optimized, multi-ROI
        - CLIP (30% weight): Zero-shot, 400M training examples
        - EasyOCR (25% weight): Multi-language, alternative OCR
    
    Voting: Weighted average of confidence scores
    
    Attributes:
        detectors: List of detector instances
        voting_method: Method for aggregating predictions
        weights: Custom weights (optional, overrides detector defaults)
    """
    
    def __init__(
        self,
        detectors: Optional[List[BaseSubtitleDetector]] = None,
        voting_method: str = 'weighted',
        custom_weights: Optional[Dict[str, float]] = None
    ):
        """
        Initialize ensemble detector.
        
        Args:
            detectors: List of detector instances (optional, creates defaults)
            voting_method: Voting method ('weighted', 'majority', 'unanimous')
            custom_weights: Custom weights dict (e.g., {'paddle': 0.4, 'clip': 0.35, ...})
        """
        if detectors is None:
            # Create default detectors
            print("[Ensemble] Initializing default detectors...")
            self.paddle = PaddleDetector(roi_mode='multi')
            self.clip = CLIPClassifier()
            self.easyocr = EasyOCRDetector(languages=['en'])
            self.detectors = [self.paddle, self.clip, self.easyocr]
            print(f"[Ensemble] Loaded {len(self.detectors)} detectors")
        else:
            self.detectors = detectors
            # Try to map detectors to attributes by model name
            for det in detectors:
                model_name = det.get_model_name()
                if model_name == 'paddle':
                    self.paddle = det
                elif model_name == 'clip':
                    self.clip = det
                elif model_name == 'easyocr':
                    self.easyocr = det
        
        self.voting_method = voting_method
        self.custom_weights = custom_weights
    
    def detect(self, video_path: str) -> Dict:
        """
        Detect subtitles using ensemble of models.
        
        Args:
            video_path: Path to video file
        
        Returns:
            {
                'has_subtitles': bool,
                'confidence': float (0-1),
                'votes': dict,  # Results from each detector
                'metadata': dict
            }
        """
        print(f"\n[Ensemble] Processing video: {video_path}")
        start_time = time.time()
        
        # Run all detectors
        votes = {}
        for detector in self.detectors:
            model_name = detector.get_model_name()
            
            print(f"[Ensemble] Running {model_name}...")
            detector_start = time.time()
            
            try:
                result = detector.detect(video_path)
                detector_time = time.time() - detector_start
                
                votes[model_name] = {
                    'has_subtitles': result['has_subtitles'],
                    'confidence': result['confidence'],
                    'weight': self.custom_weights.get(model_name, detector.get_weight()) if self.custom_weights else detector.get_weight(),
                    'metadata': result['metadata'],
                    'time': detector_time
                }
                
                print(f"[Ensemble]   {model_name}: {result['has_subtitles']} (conf: {result['confidence']:.2f}, time: {detector_time:.2f}s)")
                
            except Exception as e:
                print(f"[Ensemble]   {model_name}: ERROR - {e}")
                # Skip failed detectors (don't add to votes)
                continue
        
        # Aggregate votes
        if self.voting_method == 'weighted':
            final_result = self._weighted_voting(votes)
        elif self.voting_method == 'majority':
            final_result = self._majority_voting(votes)
        elif self.voting_method == 'unanimous':
            final_result = self._unanimous_voting(votes)
        else:
            raise ValueError(f"Unknown voting method: {self.voting_method}")
        
        total_time = time.time() - start_time
        
        # Add votes and metadata
        final_result['votes'] = votes
        final_result['metadata']['voting_method'] = self.voting_method
        final_result['metadata']['total_time'] = total_time
        final_result['metadata']['num_detectors'] = len(self.detectors)
        
        print(f"[Ensemble] Final decision: {final_result['has_subtitles']} (conf: {final_result['confidence']:.2f}, time: {total_time:.2f}s)")
        
        return final_result
    
    def _weighted_voting(self, votes: Dict) -> Dict:
        """
        Weighted average voting.
        
        Calculates weighted confidence for TRUE and FALSE separately,
        then chooses the one with higher weighted confidence.
        
        Args:
            votes: Dictionary of votes from each detector
        
        Returns:
            {
                'has_subtitles': bool,
                'confidence': float,
                'metadata': dict
            }
        """
        weighted_true = 0.0
        weighted_false = 0.0
        total_weight = 0.0
        
        for model_name, vote in votes.items():
            weight = vote['weight']
            confidence = vote['confidence']
            
            if vote['has_subtitles']:
                weighted_true += confidence * weight
            else:
                weighted_false += confidence * weight
            
            total_weight += weight
        
        # Normalize both sides
        norm_weighted_true = weighted_true / total_weight if total_weight > 0 else 0.0
        norm_weighted_false = weighted_false / total_weight if total_weight > 0 else 0.0
        
        # Decision: Choose side with higher weighted confidence
        if norm_weighted_true > norm_weighted_false:
            final_decision = True
            final_confidence = norm_weighted_true
        else:
            final_decision = False
            final_confidence = norm_weighted_false
        
        return {
            'has_subtitles': final_decision,
            'confidence': final_confidence,
            'metadata': {
                'method': 'weighted_average',
                'weighted_true': norm_weighted_true,
                'weighted_false': norm_weighted_false,
                'total_weight': total_weight
            }
        }
    
    def _majority_voting(self, votes: Dict) -> Dict:
        """
        Simple majority voting (50%+ must agree).
        
        Ignores weights, each detector has equal vote.
        Confidence = proportion of detectors that agreed with majority.
        
        Args:
            votes: Dictionary of votes from each detector
        
        Returns:
            {
                'has_subtitles': bool,
                'confidence': float,
                'metadata': dict
            }
        """
        yes_votes = sum(1 for v in votes.values() if v['has_subtitles'])
        total_votes = len(votes)
        
        final_decision = yes_votes > (total_votes / 2)
        
        # Confidence = proportion that agreed with decision
        final_confidence = yes_votes / total_votes if final_decision else (total_votes - yes_votes) / total_votes
        
        return {
            'has_subtitles': final_decision,
            'confidence': final_confidence,
            'metadata': {
                'method': 'majority',
                'yes_votes': yes_votes,
                'total_votes': total_votes,
                'vote_distribution': f'{yes_votes}/{total_votes}'
            }
        }
    
    def _unanimous_voting(self, votes: Dict) -> Dict:
        """
        Unanimous voting (all must agree).
        
        Conservative approach: only returns True if ALL detectors agree.
        Confidence = average of all detector confidences if unanimous.
        
        Args:
            votes: Dictionary of votes from each detector
        
        Returns:
            {
                'has_subtitles': bool,
                'confidence': float,
                'metadata': dict
            }
        """
        decisions = [v['has_subtitles'] for v in votes.values()]
        confidences = [v['confidence'] for v in votes.values()]
        
        # Check if all agree
        unanimous = len(set(decisions)) == 1
        
        if unanimous:
            final_decision = decisions[0]
            final_confidence = sum(confidences) / len(confidences)
        else:
            # No consensus, default to False (conservative)
            final_decision = False
            final_confidence = 0.5  # Uncertain
        
        return {
            'has_subtitles': final_decision,
            'confidence': final_confidence,
            'metadata': {
                'method': 'unanimous',
                'unanimous': unanimous,
                'decisions': decisions
            }
        }
    
    def get_detector_weights(self) -> Dict[str, float]:
        """
        Get current weights for all detectors.
        
        Returns:
            Dictionary mapping model names to weights
        """
        weights = {}
        for detector in self.detectors:
            model_name = detector.get_model_name()
            weights[model_name] = self.custom_weights.get(model_name, detector.get_weight()) if self.custom_weights else detector.get_weight()
        
        return weights
    
    def set_custom_weights(self, weights: Dict[str, float]) -> None:
        """
        Set custom weights for detectors.
        
        Args:
            weights: Dictionary mapping model names to weights
                    E.g., {'paddle': 0.4, 'clip': 0.35, 'easyocr': 0.25}
        
        Raises:
            ValueError: If weights don't sum to approximately 1.0
        """
        total = sum(weights.values())
        if not (0.95 <= total <= 1.05):  # Allow small tolerance
            raise ValueError(f"Weights must sum to ~1.0, got {total}")
        
        self.custom_weights = weights
        
        # Apply weights to each detector
        for detector in self.detectors:
            model_name = detector.get_model_name()
            if model_name in weights:
                detector.set_weight(weights[model_name])
        
        print(f"[Ensemble] Custom weights set: {weights}")
