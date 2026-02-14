"""
Voting package for ensemble decision making.

Sprint 07 - Ensemble Voting & Confidence
"""

from .advanced_voting import (
    ConfidenceWeightedVoting,
    MajorityWithThreshold,
    UnanimousConsensus
)

from .conflict_detector import ConflictDetector

from .uncertainty_estimator import UncertaintyEstimator

__all__ = [
    'ConfidenceWeightedVoting',
    'MajorityWithThreshold',
    'UnanimousConsensus',
    'ConflictDetector',
    'UncertaintyEstimator'
]

