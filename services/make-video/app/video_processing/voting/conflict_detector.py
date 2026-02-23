"""
Conflict detection for ensemble voting.

Sprint 07 - Identifies when models strongly disagree and provides conflict analysis.
"""

from typing import Dict, List
import statistics


class ConflictDetector:
    """
    Detects conflicts in ensemble votes.
    
    A conflict occurs when:
    1. Votes are divided (not unanimous or near-unanimous)
    2. At least one model has high confidence in its prediction
    
    This is critical because a simple majority might override a
    highly-confident minority model that could be correct.
    
    Example conflict:
        Model A (best): has_subs=True, conf=0.95
        Model B:        has_subs=False, conf=0.60
        Model C:        has_subs=False, conf=0.55
        
        → Conflict! Model A very confident, but outvoted 1-vs-2
    """
    
    def __init__(
        self,
        high_confidence_threshold: float = 0.80,
        conflict_margin: int = 1
    ):
        """
        Initialize conflict detector.
        
        Args:
            high_confidence_threshold: Minimum confidence to consider "high" (default: 0.80)
            conflict_margin: Max vote difference to consider "divided" (default: 1)
                             E.g., 2-vs-1 or 2-vs-2 is divided, but 3-vs-0 is not
        """
        self.high_confidence_threshold = high_confidence_threshold
        self.conflict_margin = conflict_margin
    
    def detect(self, votes: Dict) -> Dict:
        """
        Analyze votes for conflicts.
        
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
            Dictionary with conflict analysis:
                {
                    'has_conflict': bool,
                    'conflict_type': str ('divided', 'high_conf_minority', 'none'),
                    'severity': str ('high', 'medium', 'low'),
                    'yes_votes': int,
                    'no_votes': int,
                    'max_yes_confidence': float,
                    'max_no_confidence': float,
                    'confidence_spread': float,
                    'recommendations': List[str]
                }
        """
        # Separate votes by decision
        yes_votes_list = [v for v in votes.values() if v['has_subtitles']]
        no_votes_list = [v for v in votes.values() if not v['has_subtitles']]
        
        yes_count = len(yes_votes_list)
        no_count = len(no_votes_list)
        
        # Get maximum confidences for each side
        max_yes_conf = max([v['confidence'] for v in yes_votes_list], default=0.0)
        max_no_conf = max([v['confidence'] for v in no_votes_list], default=0.0)
        
        # Calculate confidence spread (std deviation)
        all_confidences = [v['confidence'] for v in votes.values()]
        confidence_spread = statistics.stdev(all_confidences) if len(all_confidences) > 1 else 0.0
        
        # Check if votes are divided
        vote_difference = abs(yes_count - no_count)
        is_divided = vote_difference <= self.conflict_margin
        
        # Check if any side has high confidence
        has_high_conf_yes = max_yes_conf >= self.high_confidence_threshold
        has_high_conf_no = max_no_conf >= self.high_confidence_threshold
        
        # Determine conflict type and severity
        has_conflict = False
        conflict_type = 'none'
        severity = 'low'
        recommendations = []
        
        if is_divided and (has_high_conf_yes or has_high_conf_no):
            has_conflict = True
            conflict_type = 'divided_high_confidence'
            
            # Determine severity
            if has_high_conf_yes and has_high_conf_no:
                severity = 'high'  # Both sides very confident → strong disagreement
                recommendations.append("Strong disagreement: Both sides have high confidence")
                recommendations.append("Consider manual review or additional evidence")
            elif vote_difference == 1:
                severity = 'medium'  # Close vote with high confidence on one side
                recommendations.append("Close vote with confident model")
                recommendations.append("Consider weighting confidence more heavily")
            else:
                severity = 'low'
        
        elif is_divided:
            has_conflict = True
            conflict_type = 'divided'
            severity = 'low'
            recommendations.append("Votes divided but no high-confidence predictions")
        
        elif confidence_spread > 0.25:
            # Large spread in confidences (even if unanimous)
            has_conflict = True
            conflict_type = 'confidence_spread'
            severity = 'low'
            recommendations.append("Large confidence spread: Models have varying certainty")
        
        # Additional recommendations based on pattern
        if max_yes_conf > 0.90 and yes_count == 1:
            recommendations.append("Single high-confidence YES vote: Consider trusting this model")
        
        if max_no_conf > 0.90 and no_count == len(votes) - 1:
            recommendations.append("Strong NO consensus: High confidence against minority")
        
        return {
            'has_conflict': has_conflict,
            'conflict_type': conflict_type,
            'severity': severity,
            'yes_votes': yes_count,
            'no_votes': no_count,
            'max_yes_confidence': max_yes_conf,
            'max_no_confidence': max_no_conf,
            'confidence_spread': confidence_spread,
            'recommendations': recommendations,
            'vote_models': {
                'yes': [model for model, v in votes.items() if v['has_subtitles']],
                'no': [model for model, v in votes.items() if not v['has_subtitles']]
            }
        }
    
    def should_fallback(self, conflict_analysis: Dict) -> bool:
        """
        Determine if ensemble should use fallback strategy based on conflict.
        
        Args:
            conflict_analysis: Output from detect()
        
        Returns:
            True if fallback recommended, False otherwise
        """
        # High severity conflicts should trigger fallback
        if conflict_analysis['severity'] == 'high':
            return True
        
        # Medium severity with very close vote
        if conflict_analysis['severity'] == 'medium' and abs(
            conflict_analysis['yes_votes'] - conflict_analysis['no_votes']
        ) <= 1:
            return True
        
        return False
    
    def get_conflict_summary(self, conflict_analysis: Dict) -> str:
        """
        Generate human-readable conflict summary.
        
        Args:
            conflict_analysis: Output from detect()
        
        Returns:
            String summary of conflict
        """
        if not conflict_analysis['has_conflict']:
            return "No conflict detected"
        
        summary_parts = [
            f"Conflict detected: {conflict_analysis['conflict_type']}",
            f"Severity: {conflict_analysis['severity']}",
            f"Vote split: {conflict_analysis['yes_votes']} YES vs {conflict_analysis['no_votes']} NO",
            f"Max YES conf: {conflict_analysis['max_yes_confidence']:.2f}",
            f"Max NO conf: {conflict_analysis['max_no_confidence']:.2f}",
            f"Confidence spread: {conflict_analysis['confidence_spread']:.3f}"
        ]
        
        if conflict_analysis['recommendations']:
            summary_parts.append("Recommendations:")
            for rec in conflict_analysis['recommendations']:
                summary_parts.append(f"  - {rec}")
        
        return "\n".join(summary_parts)
