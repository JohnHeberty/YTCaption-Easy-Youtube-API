"""
Uncertainty estimation for ensemble decisions.

Sprint 07 - Measures how uncertain the ensemble is about its decision.
"""

from typing import Dict
import statistics
import math


class UncertaintyEstimator:
    """
    Estimates uncertainty of ensemble decision.
    
    Provides multiple uncertainty metrics:
    1. Confidence spread (std dev) - How much models disagree on confidence
    2. Vote entropy - Information-theoretic measure of disagreement
    3. Margin of victory - How close the decision was
    4. Consensus score - How unified the vote was
    
    High uncertainty indicates:
    - Models disagree significantly
    - Decision was very close (e.g., 51% vs 49%)
    - Low confidence across all models
    
    Low uncertainty indicates:
    - Strong consensus (all models agree)
    - High confidence across models
    - Clear margin of victory
    """
    
    def __init__(self):
        """Initialize uncertainty estimator."""
        pass
    
    def estimate(self, votes: Dict, final_result: Dict) -> Dict:
        """
        Estimate uncertainty of ensemble decision.
        
        Args:
            votes: Dictionary of votes from ensemble
            final_result: Final decision from ensemble voting
                          (output of voting strategy)
        
        Returns:
            Dictionary with uncertainty metrics:
                {
                    'uncertainty_score': float (0-1, higher = more uncertain),
                    'confidence_spread': float,
                    'vote_entropy': float,
                    'margin_of_victory': float,
                    'consensus_score': float (0-1, higher = more consensus),
                    'uncertainty_level': str ('low', 'medium', 'high'),
                    'is_reliable': bool
                }
        """
        # Extract confidence values
        confidences = [v['confidence'] for v in votes.values()]
        decisions = [v['has_subtitles'] for v in votes.values()]
        
        # 1. Confidence Spread (Standard Deviation)
        if len(confidences) > 1:
            confidence_spread = statistics.stdev(confidences)
        else:
            confidence_spread = 0.0
        
        # 2. Vote Entropy (Shannon entropy)
        yes_count = sum(decisions)
        no_count = len(decisions) - yes_count
        total = len(decisions)
        
        if total > 0:
            p_yes = yes_count / total
            p_no = no_count / total
            
            # Shannon entropy: -sum(p * log2(p))
            entropy_terms = []
            if p_yes > 0:
                entropy_terms.append(p_yes * math.log2(p_yes))
            if p_no > 0:
                entropy_terms.append(p_no * math.log2(p_no))
            
            vote_entropy = -sum(entropy_terms) if entropy_terms else 0.0
        else:
            vote_entropy = 0.0
        
        # 3. Margin of Victory
        # For weighted voting: distance from 0.5 threshold
        final_confidence = final_result['confidence']
        margin_of_victory = abs(final_confidence - 0.5)
        
        # 4. Consensus Score
        # High consensus = all models agree + high confidence
        unanimous = (yes_count == total) or (no_count == total)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        if unanimous:
            consensus_score = avg_confidence  # Full agreement weighted by confidence
        else:
            # Partial agreement: reduce score based on split
            majority_proportion = max(yes_count, no_count) / total
            consensus_score = majority_proportion * avg_confidence
        
        # 5. Aggregate Uncertainty Score
        # Combine metrics (normalized to [0, 1])
        # Higher spread → higher uncertainty
        # Higher entropy → higher uncertainty  
        # Lower margin → higher uncertainty
        # Lower consensus → higher uncertainty
        
        spread_component = min(confidence_spread / 0.5, 1.0)  # Normalize (0.5 = max expected spread)
        entropy_component = vote_entropy  # Already [0, 1] for binary decisions
        margin_component = 1.0 - (margin_of_victory * 2)  # Invert: close to 0.5 = high uncertainty
        consensus_component = 1.0 - consensus_score  # Invert: low consensus = high uncertainty
        
        # Weighted average
        uncertainty_score = (
            0.25 * spread_component +
            0.25 * entropy_component +
            0.30 * margin_component +
            0.20 * consensus_component
        )
        
        # 6. Classify uncertainty level
        if uncertainty_score < 0.30:
            uncertainty_level = 'low'
            is_reliable = True
        elif uncertainty_score < 0.60:
            uncertainty_level = 'medium'
            is_reliable = True
        else:
            uncertainty_level = 'high'
            is_reliable = False
        
        return {
            'uncertainty_score': uncertainty_score,
            'confidence_spread': confidence_spread,
            'vote_entropy': vote_entropy,
            'margin_of_victory': margin_of_victory,
            'consensus_score': consensus_score,
            'uncertainty_level': uncertainty_level,
            'is_reliable': is_reliable,
            'metrics': {
                'num_models': len(votes),
                'yes_votes': yes_count,
                'no_votes': no_count,
                'avg_confidence': avg_confidence,
                'unanimous': unanimous
            }
        }
    
    def should_flag_uncertain(self, uncertainty_analysis: Dict) -> bool:
        """
        Determine if decision should be flagged as uncertain.
        
        Args:
            uncertainty_analysis: Output from estimate()
        
        Returns:
            True if decision is too uncertain to trust, False otherwise
        """
        # Flag if uncertainty is high OR not reliable
        return (
            uncertainty_analysis['uncertainty_level'] == 'high' or
            not uncertainty_analysis['is_reliable']
        )
    
    def get_uncertainty_summary(self, uncertainty_analysis: Dict) -> str:
        """
        Generate human-readable uncertainty summary.
        
        Args:
            uncertainty_analysis: Output from estimate()
        
        Returns:
            String summary
        """
        summary_parts = [
            f"Uncertainty Level: {uncertainty_analysis['uncertainty_level'].upper()}",
            f"Uncertainty Score: {uncertainty_analysis['uncertainty_score']:.3f}",
            f"Confidence Spread: {uncertainty_analysis['confidence_spread']:.3f}",
            f"Vote Entropy: {uncertainty_analysis['vote_entropy']:.3f}",
            f"Margin of Victory: {uncertainty_analysis['margin_of_victory']:.3f}",
            f"Consensus Score: {uncertainty_analysis['consensus_score']:.3f}",
            f"Reliable: {'YES' if uncertainty_analysis['is_reliable'] else 'NO'}"
        ]
        
        metrics = uncertainty_analysis['metrics']
        summary_parts.append(f"\nVote: {metrics['yes_votes']} YES vs {metrics['no_votes']} NO ({metrics['num_models']} models)")
        summary_parts.append(f"Average Confidence: {metrics['avg_confidence']:.3f}")
        summary_parts.append(f"Unanimous: {'YES' if metrics['unanimous'] else 'NO'}")
        
        if not uncertainty_analysis['is_reliable']:
            summary_parts.append("\n⚠️  WARNING: High uncertainty - consider manual review")
        
        return "\n".join(summary_parts)
