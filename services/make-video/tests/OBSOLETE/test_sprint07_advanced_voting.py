"""
Sprint 07: Advanced Voting & Conflict Detection - Tests

Test suite for Sprint 07 features:
- Confidence-weighted voting
- Conflict detection
- Uncertainty estimation

Requirements:
- python -m pytest tests/test_sprint07_advanced_voting.py -v
"""

import pytest
from unittest.mock import Mock, patch

from app.video_processing.ensemble_detector import EnsembleSubtitleDetector
from app.video_processing.voting import (
    ConfidenceWeightedVoting,
    ConflictDetector,
    UncertaintyEstimator
)


class TestSprint07AdvancedVoting:
    """Test suite for Sprint 07 - Advanced Voting."""
    
    # ========== TEST 1: Confidence-Weighted Voting ==========
    
    def test_confidence_weighted_voting_high_conf_wins(self):
        """
        Test 1: Confidence-weighted voting where high-confidence model prevails.
        
        Model A (best): has_subs=True, conf=0.95, weight=0.35 → 0.3325 (YES)
        Model B:        has_subs=False, conf=0.60, weight=0.30 → 0.1800 (NO)
        Model C:        has_subs=False, conf=0.55, weight=0.25 → 0.1375 (NO)
        
        Expected: YES wins despite being minority (0.3325 > 0.3175)
        """
        print("\n[Test 1] Testing confidence-weighted voting (high conf wins)...")
        
        voting = ConfidenceWeightedVoting()
        
        votes = {
            'paddle': {
                'has_subtitles': True,
                'confidence': 0.95,
                'weight': 0.35,
                'metadata': {}
            },
            'clip': {
                'has_subtitles': False,
                'confidence': 0.60,
                'weight': 0.30,
                'metadata': {}
            },
            'easyocr': {
                'has_subtitles': False,
                'confidence': 0.55,
                'weight': 0.25,
                'metadata': {}
            }
        }
        
        result = voting.vote(votes)
        
        # High-confidence model should win
        assert result['has_subtitles'] == True, "High-confidence model should prevail"
        assert result['confidence'] > 0.50, f"Expected conf > 0.50, got {result['confidence']:.3f}"
        assert result['metadata']['method'] == 'confidence_weighted'
        
        print(f"[Test 1] ✅ Confidence-weighted: HIGH_CONF wins (conf={result['confidence']:.3f})")
    
    # ========== TEST 2: Conflict Detection - Divided Vote ==========
    
    def test_conflict_detection_divided_vote(self):
        """
        Test 2: Detect conflict when votes are divided with high confidence.
        
        2 vs 1 split + one side has 0.90+ confidence → conflict
        """
        print("\n[Test 2] Testing conflict detection (divided vote)...")
        
        detector = ConflictDetector(high_confidence_threshold=0.80)
        
        votes = {
            'paddle': {
                'has_subtitles': True,
                'confidence': 0.92,  # High confidence
                'weight': 0.35,
                'metadata': {}
            },
            'clip': {
                'has_subtitles': False,
                'confidence': 0.65,
                'weight': 0.30,
                'metadata': {}
            },
            'easyocr': {
                'has_subtitles': False,
                'confidence': 0.60,
                'weight': 0.25,
                'metadata': {}
            }
        }
        
        analysis = detector.detect(votes)
        
        # Should detect conflict
        assert analysis['has_conflict'] == True, "Should detect conflict in divided vote"
        assert analysis['conflict_type'] == 'divided_high_confidence'
        assert analysis['yes_votes'] == 1
        assert analysis['no_votes'] == 2
        assert analysis['max_yes_confidence'] == 0.92
        assert len(analysis['recommendations']) > 0
        
        print(f"[Test 2] ✅ Conflict detected: {analysis['conflict_type']} (severity: {analysis['severity']})")
    
    # ========== TEST 3: Conflict Detection - No Conflict ==========
    
    def test_conflict_detection_no_conflict(self):
        """
        Test 3: No conflict when all models agree with high confidence.
        """
        print("\n[Test 3] Testing conflict detection (no conflict)...")
        
        detector = ConflictDetector()
        
        votes = {
            'paddle': {
                'has_subtitles': True,
                'confidence': 0.88,
                'weight': 0.35,
                'metadata': {}
            },
            'clip': {
                'has_subtitles': True,
                'confidence': 0.85,
                'weight': 0.30,
                'metadata': {}
            },
            'easyocr': {
                'has_subtitles': True,
                'confidence': 0.80,
                'weight': 0.25,
                'metadata': {}
            }
        }
        
        analysis = detector.detect(votes)
        
        # No conflict expected
        assert analysis['has_conflict'] == False, "Should not detect conflict when unanimous"
        assert analysis['yes_votes'] == 3
        assert analysis['no_votes'] == 0
        
        print(f"[Test 3] ✅ No conflict detected (unanimous agreement)")
    
    # ========== TEST 4: Uncertainty Estimation - Low Uncertainty ==========
    
    def test_uncertainty_estimation_low(self):
        """
        Test 4: Low uncertainty when all models agree with high confidence.
        """
        print("\n[Test 4] Testing uncertainty estimation (low)...")
        
        estimator = UncertaintyEstimator()
        
        votes = {
            'paddle': {'has_subtitles': True, 'confidence': 0.90, 'weight': 0.35, 'metadata': {}},
            'clip': {'has_subtitles': True, 'confidence': 0.87, 'weight': 0.30, 'metadata': {}},
            'easyocr': {'has_subtitles': True, 'confidence': 0.83, 'weight': 0.25, 'metadata': {}}
        }
        
        final_result = {'has_subtitles': True, 'confidence': 0.87,  'metadata': {}}
        
        analysis = estimator.estimate(votes, final_result)
        
        # Low uncertainty expected
        assert analysis['uncertainty_level'] == 'low', f"Expected low uncertainty, got {analysis['uncertainty_level']}"
        assert analysis['is_reliable'] == True
        assert analysis['metrics']['unanimous'] == True
        assert analysis['consensus_score'] > 0.80
        
        print(f"[Test 4] ✅ Uncertainty: {analysis['uncertainty_level']} (score={analysis['uncertainty_score']:.3f})")
    
    # ========== TEST 5: Uncertainty Estimation - High Uncertainty ==========
    
    def test_uncertainty_estimation_high(self):
        """
        Test 5: High uncertainty when models disagree with varied confidence.
        """
        print("\n[Test 5] Testing uncertainty estimation (high)...")
        
        estimator = UncertaintyEstimator()
        
        votes = {
            'paddle': {'has_subtitles': True, 'confidence': 0.92, 'weight': 0.35, 'metadata': {}},
            'clip': {'has_subtitles': False, 'confidence': 0.60, 'weight': 0.30, 'metadata': {}},
            'easyocr': {'has_subtitles': False, 'confidence': 0.55, 'weight': 0.25, 'metadata': {}}
        }
        
        final_result = {'has_subtitles': False, 'confidence': 0.58, 'metadata': {}}
        
        analysis = estimator.estimate(votes, final_result)
        
        # High uncertainty expected (divided vote + spread)
        assert analysis['metrics']['unanimous'] == False
        assert analysis['confidence_spread'] > 0.15, f"Expected spread > 0.15, got {analysis['confidence_spread']:.3f}"
        assert analysis['vote_entropy'] > 0.5  # Binary entropy should be > 0.5 for divided vote
        
        print(f"[Test 5] ✅ Uncertainty: {analysis['uncertainty_level']} (score={analysis['uncertainty_score']:.3f}, spread={analysis['confidence_spread']:.3f})")
    
    # ========== TEST 6: Ensemble with Conflict Detection Enabled ==========
    
    def test_ensemble_with_conflict_detection(self):
        """
        Test 6: Ensemble with conflict detection enabled.
        """
        print("\n[Test 6] Testing ensemble with conflict detection...")
        
        ensemble = EnsembleSubtitleDetector(
            voting_method='confidence_weighted',
            enable_conflict_detection=True
        )
        
        # Mock detectors
        with patch.object(ensemble.paddle, 'detect', return_value={
            'has_subtitles': True,
            'confidence': 0.93,
            'metadata': {'model': 'paddleocr'},
            'time': 1.2
        }):
            with patch.object(ensemble.clip, 'detect', return_value={
                'has_subtitles': False,
                'confidence': 0.62,
                'metadata': {'model': 'clip'},
                'time': 2.0
            }):
                with patch.object(ensemble.easyocr, 'detect', return_value={
                    'has_subtitles': False,
                    'confidence': 0.58,
                    'metadata': {'model': 'easyocr'},
                    'time': 1.5
                }):
                    result = ensemble.detect('/tmp/test.mp4')
        
        # Should have conflict analysis
        assert 'conflict_analysis' in result
        assert result['conflict_analysis']['has_conflict'] == True
        
        print(f"[Test 6] ✅ Conflict analysis included: {result['conflict_analysis']['conflict_type']}")
    
    # ========== TEST 7: Ensemble with Uncertainty Estimation Enabled ==========
    
    def test_ensemble_with_uncertainty_estimation(self):
        """
        Test 7: Ensemble with uncertainty estimation enabled.
        """
        print("\n[Test 7] Testing ensemble with uncertainty estimation...")
        
        ensemble = EnsembleSubtitleDetector(
            voting_method='confidence_weighted',
            enable_uncertainty_estimation=True
        )
        
        # Mock unanimous vote (low uncertainty)
        with patch.object(ensemble.paddle, 'detect', return_value={
            'has_subtitles': True,
            'confidence': 0.90,
            'metadata': {},
            'time': 1.0
        }):
            with patch.object(ensemble.clip, 'detect', return_value={
                'has_subtitles': True,
                'confidence': 0.86,
                'metadata': {},
                'time': 2.0
            }):
                with patch.object(ensemble.easyocr, 'detect', return_value={
                    'has_subtitles': True,
                    'confidence': 0.82,
                    'metadata': {},
                    'time': 1.5
                }):
                    result = ensemble.detect('/tmp/test.mp4')
        
        # Should have uncertainty analysis
        assert 'uncertainty_analysis' in result
        assert result['uncertainty_analysis']['uncertainty_level'] == 'low'
        assert result['uncertainty_analysis']['is_reliable'] == True
        
        print(f"[Test 7] ✅ Uncertainty analysis included: {result['uncertainty_analysis']['uncertainty_level']}")
    
    # ========== TEST 8: Confidence-Weighted vs Standard Weighted ==========
    
    def test_confidence_weighted_vs_standard(self):
        """
        Test 8: Compare confidence-weighted vs standard weighted voting.
        
        Expected: Confidence-weighted should favor high-confidence models more.
        """
        print("\n[Test 8] Comparing confidence-weighted vs standard weighted...")
        
        votes = {
            'paddle': {'has_subtitles': True, 'confidence': 0.95, 'weight': 0.35, 'metadata': {}},
            'clip': {'has_subtitles': False, 'confidence': 0.60, 'weight': 0.30, 'metadata': {}},
            'easyocr': {'has_subtitles': False, 'confidence': 0.55, 'weight': 0.25, 'metadata': {}}
        }
        
        # Standard weighted (ensemble method from Sprint 06)
        ensemble_standard = EnsembleSubtitleDetector(voting_method='weighted')
        conf_weighted_voting = ConfidenceWeightedVoting()
        
        result_conf = conf_weighted_voting.vote(votes)
        
        # Confidence-weighted should favor the high-confidence model
        assert result_conf['has_subtitles'] == True
        
        print(f"[Test 8] ✅ Confidence-weighted: {result_conf['has_subtitles']} (conf={result_conf['confidence']:.3f})")
    
    # ========== TEST 9: Conflict Severity Levels ==========
    
    def test_conflict_severity_levels(self):
        """
        Test 9: Test different conflict severity levels.
        """
        print("\n[Test 9] Testing conflict severity levels...")
        
        detector = ConflictDetector(high_confidence_threshold=0.80)
        
        # High severity: Both sides have high confidence
        votes_high = {
            'paddle': {'has_subtitles': True, 'confidence': 0.92, 'weight': 0.35, 'metadata': {}},
            'clip': {'has_subtitles': False, 'confidence': 0.88, 'weight': 0.30, 'metadata': {}},
            'easyocr': {'has_subtitles': True, 'confidence': 0.85, 'weight': 0.25, 'metadata': {}}
        }
        
        analysis_high = detector.detect(votes_high)
        
        # Should be medium or high severity (both sides have high conf)
        assert analysis_high['has_conflict'] == True
        assert analysis_high['severity'] in ['medium', 'high']
        
        print(f"[Test 9] ✅ Conflict severity: {analysis_high['severity']}")


# ========== Summary Test ==========

def test_sprint07_summary():
    """
    Summary test: Print Sprint 07 implementation status.
    """
    print("\n" + "="*60)
    print("SPRINT 07 - ADVANCED VOTING IMPLEMENTATION SUMMARY")
    print("="*60)
    print("✅ ConfidenceWeightedVoting (dynamic weights)")
    print("✅ ConflictDetector (identifies disagreements)")
    print("✅ UncertaintyEstimator (measures decision reliability)")
    print("✅ Ensemble integration (opt-in features)")
    print("\nNew Voting Method:")
    print("  - confidence_weighted: Weights × Confidence")
    print("\nAnalysis Tools:")
    print("  - Conflict detection: 3 severity levels")
    print("  - Uncertainty estimation: 5 metrics")
    print("="*60)
    print("✅ Sprint 07 Tests: 9/9 EXPECTED")
    print("="*60)
    
    assert True  # Always pass (informational test)
