"""
Sprint 06: Ensemble de Modelos Pré-Treinados - Tests

Test suite for ensemble detection system (PaddleOCR + CLIP + EasyOCR).

Requirements:
- python -m pytest tests/test_sprint06_ensemble.py -v
- Requires: torch, transformers, easyocr
"""

import pytest
import json
import os
import glob
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from app.video_processing.ensemble_detector import EnsembleSubtitleDetector
from app.video_processing.detectors.paddle_detector import PaddleDetector
from app.video_processing.detectors.clip_classifier import CLIPClassifier
from app.video_processing.detectors.easyocr_detector import EasyOCRDetector


# ========== Mock Fixtures ==========


class TestSprint06Ensemble:
    """Test suite for Sprint 06 - Ensemble System."""
    
    # ========== TEST 1: Individual Detector - Paddle ==========
    
    def test_paddle_detector_individual(self, video_with_subs, video_without_subs):
        """
        Test 1: PaddleDetector standalone functionality.
        
        Ensures Sprint 00-04 integration works correctly.
        """
        print("\n[Test 1] Testing PaddleDetector individual...")
        
        detector = PaddleDetector(roi_mode='multi')
        
        # Test WITH subtitles
        result_with = detector.detect(video_with_subs)
        
        assert 'has_subtitles' in result_with
        assert 'confidence' in result_with
        assert 'metadata' in result_with
        
        # Should detect subtitles
        assert result_with['has_subtitles'] == True, "Paddle should detect subtitles in video_with_subs_1.mp4"
        assert result_with['confidence'] > 0.7, f"Confidence too low: {result_with['confidence']}"
        
        # Metadata checks
        assert result_with['metadata']['model'] == 'paddleocr'
        assert result_with['metadata']['roi_mode'] == 'multi'
        
        # Test WITHOUT subtitles
        result_without = detector.detect(video_without_subs)
        
        # Should NOT detect subtitles
        assert result_without['has_subtitles'] == False, "Paddle should NOT detect subtitles in video_without_subs_1.mp4"
        
        print("[Test 1] ✅ PaddleDetector working correctly")
    
    # ========== TEST 2: Individual Detector - CLIP ==========
    
    def test_clip_classifier_individual(self, video_with_subs, video_without_subs):
        """
        Test 2: CLIPClassifier standalone functionality.
        
        Tests zero-shot classification with CLIP model.
        """
        print("\n[Test 2] Testing CLIPClassifier individual...")
        
        classifier = CLIPClassifier()
        
        # Test WITH subtitles
        result_with = classifier.detect(video_with_subs)
        
        assert 'has_subtitles' in result_with
        assert 'confidence' in result_with
        assert 'metadata' in result_with
        
        # CLIP may not be as accurate as Paddle on first video,
        # but should work and return valid response
        assert isinstance(result_with['has_subtitles'], bool)
        assert 0.0 <= result_with['confidence'] <= 1.0
        
        # Metadata checks
        assert result_with['metadata']['model'] == 'clip'
        assert 'frame_results' in result_with['metadata']
        assert 'votes' in result_with['metadata']
        
        # Test WITHOUT subtitles
        result_without = classifier.detect(video_without_subs)
        
        assert isinstance(result_without['has_subtitles'], bool)
        
        print("[Test 2] ✅ CLIPClassifier working correctly")
    
    # ========== TEST 3: Individual Detector - EasyOCR ==========
    
    def test_easyocr_detector_individual(self, video_with_subs, video_without_subs):
        """
        Test 3: EasyOCRDetector standalone functionality.
        
        Tests alternative OCR engine.
        """
        print("\n[Test 3] Testing EasyOCRDetector individual...")
        
        detector = EasyOCRDetector(languages=['en'])
        
        # Test WITH subtitles
        result_with = detector.detect(video_with_subs)
        
        assert 'has_subtitles' in result_with
        assert 'confidence' in result_with
        assert 'metadata' in result_with
        
        # EasyOCR should work (may have different accuracy than Paddle)
        assert isinstance(result_with['has_subtitles'], bool)
        assert 0.0 <= result_with['confidence'] <= 1.0
        
        # Metadata checks
        assert result_with['metadata']['model'] == 'easyocr'
        assert 'frame_results' in result_with['metadata']
        
        # Test WITHOUT subtitles
        result_without = detector.detect(video_without_subs)
        
        assert isinstance(result_without['has_subtitles'], bool)
        
        print("[Test 3] ✅ EasyOCRDetector working correctly")
    
    # ========== TEST 4: Ensemble Weighted Voting ==========
    
    def test_ensemble_weighted_voting(self, ensemble_detector, video_with_subs):
        """
        Test 4: Ensemble with weighted voting on video WITH subtitles.
        
        All detectors should vote, and ensemble should detect subtitles.
        """
        print("\n[Test 4] Testing Ensemble weighted voting...")
        
        result = ensemble_detector.detect(video_with_subs)
        
        # Check result structure
        assert 'has_subtitles' in result
        assert 'confidence' in result
        assert 'votes' in result
        assert 'metadata' in result
        
        # Check that all 3 models voted
        assert 'paddle' in result['votes']
        assert 'clip' in result['votes']
        assert 'easyocr' in result['votes']
        
        # Each vote should have required fields
        for model_name, vote in result['votes'].items():
            assert 'has_subtitles' in vote
            assert 'confidence' in vote
            assert 'weight' in vote
            assert 'metadata' in vote
        
        # Ensemble should detect subtitles (video has them)
        assert result['has_subtitles'] == True, f"Ensemble failed to detect subtitles (conf: {result['confidence']})"
        assert result['confidence'] > 0.5, f"Confidence too low: {result['confidence']}"
        
        # Metadata checks
        assert result['metadata']['voting_method'] == 'weighted'
        assert result['metadata']['num_detectors'] == 3
        
        print(f"[Test 4] ✅ Ensemble detected: {result['has_subtitles']} (conf: {result['confidence']:.2f})")
    
    # ========== TEST 5: Ensemble Consensus ==========
    
    def test_ensemble_consensus(self, ensemble_detector, video_without_subs):
        """
        Test 5: Ensemble consensus on video WITHOUT subtitles.
        
        All (or most) detectors should agree that there are no subtitles.
        """
        print("\n[Test 5] Testing Ensemble consensus (no subtitles)...")
        
        result = ensemble_detector.detect(video_without_subs)
        
        # Count how many detectors voted "no subtitles"
        no_votes = sum(1 for v in result['votes'].values() if not v['has_subtitles'])
        total_votes = len(result['votes'])
        
        print(f"[Test 5] Vote distribution: {no_votes}/{total_votes} voted 'no subtitles'")
        
        # Ensemble should NOT detect subtitles (video doesn't have them)
        # Allow some tolerance (2/3 or more must agree)
        assert no_votes >= 2, f"Not enough detectors agreed (only {no_votes}/3)"
        
        # Final decision should be False
        assert result['has_subtitles'] == False, "Ensemble incorrectly detected subtitles"
        
        print(f"[Test 5] ✅ Ensemble correctly rejected (conf: {result['confidence']:.2f})")
    
    # ========== TEST 6: Ensemble vs Paddle Alone ==========
    
    def test_ensemble_vs_paddle_alone(self, video_with_subs):
        """
        Test 6: Compare ensemble vs PaddleOCR alone.
        
        Both should detect, but ensemble may have different confidence.
        """
        print("\n[Test 6] Comparing Ensemble vs Paddle alone...")
        
        # Paddle alone
        paddle = PaddleDetector(roi_mode='multi')
        paddle_result = paddle.detect(video_with_subs)
        
        # Ensemble
        ensemble = EnsembleSubtitleDetector()
        ensemble_result = ensemble.detect(video_with_subs)
        
        # Both should detect subtitles
        assert paddle_result['has_subtitles'] == ensemble_result['has_subtitles'], \
            f"Mismatch: Paddle={paddle_result['has_subtitles']}, Ensemble={ensemble_result['has_subtitles']}"
        
        # Log confidence comparison
        print(f"[Test 6] Paddle confidence: {paddle_result['confidence']:.3f}")
        print(f"[Test 6] Ensemble confidence: {ensemble_result['confidence']:.3f}")
        print(f"[Test 6] Difference: {abs(ensemble_result['confidence'] - paddle_result['confidence']):.3f}")
        
        # Both should be reasonably confident
        assert paddle_result['confidence'] > 0.7
        assert ensemble_result['confidence'] > 0.5  # Ensemble may be more conservative
        
        print("[Test 6] ✅ Ensemble vs Paddle comparison OK")
    
    # ========== TEST 7: Ensemble on Multiple Videos ==========
    
    def test_ensemble_on_multiple_videos(self, ensemble_detector, ground_truth):
        """
        Test 7: Ensemble on subset of validation videos (10 videos).
        
        Tests accuracy on diverse dataset.
        """
        print("\n[Test 7] Testing Ensemble on multiple videos...")
        
        # Select subset of videos (10 videos for speed)
        # 5 with subtitles + 5 without
        with_subs = [path for path, label in list(ground_truth.items())[:20] if label and os.path.exists(path)][:5]
        without_subs = [path for path, label in list(ground_truth.items())[:20] if not label and os.path.exists(path)][:5]
        
        test_videos = with_subs + without_subs
        
        if len(test_videos) < 8:
            pytest.skip("Not enough test videos available")
        
        print(f"[Test 7] Testing on {len(test_videos)} videos...")
        
        results = []
        for video_path in test_videos:
            expected = ground_truth[video_path]
            result = ensemble_detector.detect(video_path)
            
            correct = (result['has_subtitles'] == expected)
            results.append({
                'video': video_path,
                'expected': expected,
                'predicted': result['has_subtitles'],
                'confidence': result['confidence'],
                'correct': correct
            })
            
            status = "✅" if correct else "❌"
            print(f"  {status} {Path(video_path).name}: expected={expected}, got={result['has_subtitles']} (conf={result['confidence']:.2f})")
        
        # Calculate accuracy
        accuracy = sum(1 for r in results if r['correct']) / len(results)
        
        print(f"\n[Test 7] Accuracy: {accuracy:.1%} ({sum(1 for r in results if r['correct'])}/{len(results)})")
        
        # Ensemble should have decent accuracy (>= 70% on diverse dataset)
        assert accuracy >= 0.70, f"Accuracy too low: {accuracy:.1%}"
        
        print("[Test 7] ✅ Ensemble tested on multiple videos")
    
    # ========== TEST 8: Ensemble Performance ==========
    
    def test_ensemble_performance(self, ensemble_detector, video_with_subs):
        """
        Test 8: Ensemble performance (should complete in <30s).
        
        Ensemble runs 3 models, so it's slower than single model.
        """
        print("\n[Test 8] Testing Ensemble performance...")
        
        import time
        
        start = time.time()
        result = ensemble_detector.detect(video_with_subs)
        elapsed = time.time() - start
        
        print(f"[Test 8] Ensemble time: {elapsed:.2f}s")
        print(f"[Test 8] Per-detector times:")
        for model_name, vote in result['votes'].items():
            detector_time = vote.get('time', 0)
            print(f"  - {model_name}: {detector_time:.2f}s")
        
        # Ensemble should complete in reasonable time
        # Allow 30s (3 models × ~10s each, sequential)
        assert elapsed < 30.0, f"Ensemble too slow: {elapsed:.2f}s (expected <30s)"
        
        print(f"[Test 8] ✅ Ensemble performance OK ({elapsed:.2f}s < 30s)")
    
    # ========== TEST 9: Ensemble on Edge Cases ==========
    
    def test_ensemble_on_edge_cases(self, ensemble_detector):
        """
        Test 9: Ensemble on edge case videos (Sprint 04).
        
        Tests non-standard subtitle positions.
        """
        print("\n[Test 9] Testing Ensemble on edge cases...")
        
        # Edge case videos from Sprint 04
        edge_case_videos = [
            "storage/validation/edge_cases/top/video_with_top_subs_1.mp4",
            "storage/validation/edge_cases/left/video_with_left_text_1.mp4",
            "storage/validation/edge_cases/right/video_with_right_text_1.mp4",
            "storage/validation/edge_cases/center/video_with_center_text_1.mp4"
        ]
        
        # Filter existing videos
        existing_videos = [v for v in edge_case_videos if os.path.exists(v)]
        
        if len(existing_videos) < 2:
            pytest.skip("Not enough edge case videos available")
        
        print(f"[Test 9] Testing {len(existing_videos)} edge case videos...")
        
        results = []
        for video_path in existing_videos:
            result = ensemble_detector.detect(video_path)
            
            results.append({
                'video': Path(video_path).name,
                'predicted': result['has_subtitles'],
                'confidence': result['confidence']
            })
            
            # All edge case videos have text (expected=True)
            status = "✅" if result['has_subtitles'] else "❌"
            print(f"  {status} {Path(video_path).name}: {result['has_subtitles']} (conf={result['confidence']:.2f})")
        
        # At least 50% should be detected (ensemble may miss some edge cases)
        detected = sum(1 for r in results if r['predicted'])
        detection_rate = detected / len(results) if results else 0
        
        print(f"\n[Test 9] Detection rate on edge cases: {detection_rate:.1%} ({detected}/{len(results)})")
        
        # Allow some edge cases to be missed (ensemble may be conservative)
        assert detection_rate >= 0.50, f"Edge case detection too low: {detection_rate:.1%}"
        
        print("[Test 9] ✅ Ensemble tested on edge cases")
    
    # ========== TEST 10: Ensemble Voting Methods ==========
    
    def test_ensemble_voting_methods(self, video_with_subs):
        """
        Test 10: Test different voting methods (weighted, majority, unanimous).
        
        All methods should work and produce valid results.
        """
        print("\n[Test 10] Testing different voting methods...")
        
        methods = ['weighted', 'majority', 'unanimous']
        
        for method in methods:
            print(f"\n[Test 10] Testing voting method: {method}")
            
            ensemble = EnsembleSubtitleDetector(voting_method=method)
            result = ensemble.detect(video_with_subs)
            
            # Check result structure
            assert 'has_subtitles' in result
            assert 'confidence' in result
            assert result['metadata']['voting_method'] == method
            
            print(f"  {method}: {result['has_subtitles']} (conf={result['confidence']:.2f})")
        
        print("\n[Test 10] ✅ All voting methods working")


# ========== Integration Test (OPTIONAL - Manual Run) ==========

@pytest.mark.slow
def test_ensemble_full_dataset_accuracy(ensemble_detector, ground_truth):
    """
    SLOW TEST: Test ensemble on FULL dataset (all 83+ videos).
    
    Run with: pytest tests/test_sprint06_ensemble.py::test_ensemble_full_dataset_accuracy -v -s
    
    Goal: ≥90% accuracy on full dataset.
    """
    print("\n[SLOW TEST] Testing Ensemble on FULL dataset...")
    print(f"Total videos in ground truth: {len(ground_truth)}")
    
    # Filter existing videos
    existing_videos = {path: label for path, label in ground_truth.items() if os.path.exists(path)}
    
    if len(existing_videos) < 50:
        pytest.skip(f"Not enough videos available (found {len(existing_videos)}, need ≥50)")
    
    print(f"Testing on {len(existing_videos)} existing videos...")
    
    results = []
    for i, (video_path, expected) in enumerate(existing_videos.items(), 1):
        print(f"\n[{i}/{len(existing_videos)}] Processing: {Path(video_path).name}")
        
        result = ensemble_detector.detect(video_path)
        correct = (result['has_subtitles'] == expected)
        
        results.append({
            'video': video_path,
            'expected': expected,
            'predicted': result['has_subtitles'],
            'confidence': result['confidence'],
            'correct': correct
        })
        
        status = "✅" if correct else "❌"
        print(f"  {status} Expected={expected}, Got={result['has_subtitles']} (conf={result['confidence']:.2f})")
    
    # Calculate metrics
    accuracy = sum(1 for r in results if r['correct']) / len(results)
    
    # Confusion matrix
    tp = sum(1 for r in results if r['expected'] and r['predicted'])
    fp = sum(1 for r in results if not r['expected'] and r['predicted'])
    tn = sum(1 for r in results if not r['expected'] and not r['predicted'])
    fn = sum(1 for r in results if r['expected'] and not r['predicted'])
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"\n{'='*60}")
    print(f"ENSEMBLE FULL DATASET RESULTS")
    print(f"{'='*60}")
    print(f"Total videos: {len(results)}")
    print(f"Accuracy: {accuracy:.1%} ({sum(1 for r in results if r['correct'])}/{len(results)})")
    print(f"Precision: {precision:.1%}")
    print(f"Recall: {recall:.1%}")
    print(f"F1 Score: {f1:.1%}")
    print(f"\nConfusion Matrix:")
    print(f"  TP: {tp}  FP: {fp}")
    print(f"  FN: {fn}  TN: {tn}")
    print(f"{'='*60}")
    
    # List errors
    errors = [r for r in results if not r['correct']]
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for err in errors:
            print(f"  ❌ {Path(err['video']).name}: expected={err['expected']}, got={err['predicted']} (conf={err['confidence']:.2f})")
    
    # Goal: ≥90% accuracy
    assert accuracy >= 0.90, f"Accuracy below target: {accuracy:.1%} (goal: ≥90%)"
    
    print(f"\n✅ ENSEMBLE ACHIEVES ≥90% ACCURACY!")
