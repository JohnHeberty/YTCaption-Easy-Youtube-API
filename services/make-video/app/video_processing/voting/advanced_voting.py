"""
Advanced voting strategies for ensemble detection.

Sprint 07 - Confidence-Weighted Voting
Improves upon simple weighted average by considering confidence of each prediction.
"""

from typing import Dict, Tuple


class ConfidenceWeightedVoting:
    """
    Confidence-weighted voting strategy.
    
    Unlike simple weighted voting (where weights are fixed per model),
    this strategy gives MORE influence to predictions with HIGHER confidence.
    
    Formula: dynamic_weight = confidence × base_weight
    
    Example:
        Model A: has_subs=True, conf=0.95, weight=0.35 → 0.3325 (YES)
        Model B: has_subs=False, conf=0.60, weight=0.30 → 0.1800 (NO)
        Model C: has_subs=False, conf=0.55, weight=0.25 → 0.1375 (NO)
        
        YES score: 0.3325
        NO score:  0.3175
        Decision: YES (0.3325 > 0.3175) ✅ High-confidence model prevails!
    """
    
    def __init__(self, name: str = 'confidence_weighted'):
        """
        Initialize confidence-weighted voting.
        
        Args:
            name: Strategy name for metadata
        """
        self.name = name
    
    def vote(self, votes: Dict) -> Dict:
        """
        Compute confidence-weighted vote.
        
        Args:
            votes: Dictionary of votes from ensemble
                   Format: {
                       'model_name': {
                           'has_subtitles': bool,
                           'confidence': float,
                           'weight': float,
                           ...
                       },
                       ...
                   }
        
        Returns:
            Dictionary with:
                'has_subtitles': bool - Final decision
                'confidence': float - Normalized confidence score
                'metadata': dict - Voting details
        """
        yes_score = 0.0
        no_score = 0.0
        
        # Calculate dynamic weights for each vote
        for model_name, vote in votes.items():
            # Dynamic weight = confidence × base_weight
            dynamic_weight = vote['confidence'] * vote['weight']
            
            if vote['has_subtitles']:
                yes_score += dynamic_weight
            else:
                no_score += dynamic_weight
        
        # Normalize to [0, 1]
        total_score = yes_score + no_score
        
        if total_score > 0:
            final_confidence = yes_score / total_score
            final_decision = final_confidence >= 0.5
        else:
            # Edge case: all votes have 0 confidence
            final_confidence = 0.5
            final_decision = False
        
        return {
            'has_subtitles': final_decision,
            'confidence': final_confidence,
            'metadata': {
                'method': self.name,
                'yes_score': yes_score,
                'no_score': no_score,
                'total_score': total_score
            }
        }


class MajorityWithThreshold:
    """
    Majority voting with minimum confidence threshold.
    
    Decision by simple majority (50%+ models agree),
    but only if average confidence of majority ≥ threshold.
    
    This prevents low-confidence majority decisions.
    """
    
    def __init__(self, min_avg_confidence: float = 0.65, name: str = 'majority_threshold'):
        """
        Initialize majority voting with threshold.
        
        Args:
            min_avg_confidence: Minimum average confidence for majority (default: 0.65)
            name: Strategy name
        """
        self.min_avg_confidence = min_avg_confidence
        self.name = name
    
    def vote(self, votes: Dict) -> Dict:
        """
        Compute majority vote with confidence check.
        
        Args:
            votes: Dictionary of votes from ensemble
        
        Returns:
            Dictionary with decision and confidence, or None if threshold not met
        """
        # Count votes
        yes_votes = sum(1 for v in votes.values() if v['has_subtitles'])
        no_votes = len(votes) - yes_votes
        
        # Determine majority
        final_decision = yes_votes > no_votes
        
        # Get majority votes
        majority_votes = [
            v for v in votes.values() 
            if v['has_subtitles'] == final_decision
        ]
        
        # Calculate average confidence of majority
        if majority_votes:
            avg_confidence = sum(v['confidence'] for v in majority_votes) / len(majority_votes)
        else:
            avg_confidence = 0.0
        
        # Check threshold
        meets_threshold = avg_confidence >= self.min_avg_confidence
        
        if not meets_threshold:
            # Majority confidence too low → uncertain
            return {
                'has_subtitles': final_decision,
                'confidence': avg_confidence,
                'metadata': {
                    'method': self.name,
                    'warning': 'low_confidence_majority',
                    'avg_confidence': avg_confidence,
                    'threshold': self.min_avg_confidence,
                    'meets_threshold': False
                }
            }
        
        return {
            'has_subtitles': final_decision,
            'confidence': avg_confidence,
            'metadata': {
                'method': self.name,
                'yes_votes': yes_votes,
                'no_votes': no_votes,
                'avg_confidence': avg_confidence,
                'meets_threshold': True
            }
        }


class UnanimousConsensus:
    """
    Unanimous consensus strategy (fast path).
    
    If ALL models agree with high confidence (≥ min_confidence),
    return decision immediately without complex voting.
    
    This is an optimization for obvious cases.
    """
    
    def __init__(self, min_confidence: float = 0.75, name: str = 'unanimous'):
        """
        Initialize unanimous consensus.
        
        Args:
            min_confidence: Minimum confidence required for each model (default: 0.75)
            name: Strategy name
        """
        self.min_confidence = min_confidence
        self.name = name
    
    def vote(self, votes: Dict) -> Dict:
        """
        Check for unanimous consensus.
        
        Args:
            votes: Dictionary of votes from ensemble
        
        Returns:
            Dictionary with decision if unanimous, None otherwise
        """
        decisions = [v['has_subtitles'] for v in votes.values()]
        confidences = [v['confidence'] for v in votes.values()]
        
        # Check unanimity
        unanimous = len(set(decisions)) == 1
        
        # Check confidence threshold
        high_confidence = all(c >= self.min_confidence for c in confidences)
        
        if unanimous and high_confidence:
            final_decision = decisions[0]
            avg_confidence = sum(confidences) / len(confidences)
            
            return {
                'has_subtitles': final_decision,
                'confidence': avg_confidence,
                'metadata': {
                    'method': self.name,
                    'consensus': True,
                    'min_confidence': self.min_confidence,
                    'num_models': len(votes)
                }
            }
        
        # No consensus → return None (fallback to next strategy)
        return None
