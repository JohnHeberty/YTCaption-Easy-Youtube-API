"""
Sprint 02 Test Suite - Advanced Preprocessing

Tests preprocessing techniques on low-quality videos:
- Low contrast (dark text on dark background)
- Compressed (JPEG artifacts)
- Motion blur
- Noisy (high grain)
- Low resolution (upscaled)
- Combined (multiple degradations)

Validates:
1. Maintains 100% accuracy on high-quality videos (Sprint 00/01 regression)
2. Improves accuracy on low-quality videos with preprocessing
3. Different preprocessing presets work correctly
4. Processing time remains acceptable (<10s per video)
"""

import pytest
import sys
from pathlib import Path
import json
import time

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2
from app.video_processing.frame_preprocessor import FramePreprocessor


class TestSprint02Preprocessing:
    """Sprint 02: Advanced Preprocessing Tests"""
    
    @pytest.fixture(scope='class')
    def low_quality_dataset(self):
        """Load low-quality dataset ground truth"""
        gt_path = Path('storage/validation/low_quality/ground_truth.json')
        
        if not gt_path.exists():
            pytest.skip("Low-quality dataset not found. Run: python scripts/generate_low_quality_dataset.py")
        
        with open(gt_path) as f:
            return json.load(f)
    
    @pytest.fixture(scope='class')
    def high_quality_dataset(self):
        """Load multi-resolution dataset (Sprint 01) for regression testing"""
        gt_path = Path('storage/validation/multi_resolution/ground_truth.json')
        
        if not gt_path.exists():
            pytest.skip("Multi-resolution dataset not found.")
        
        with open(gt_path) as f:
            return json.load(f)
    
    def test_preprocessing_module_presets(self):
        """Test that all preprocessing presets can be created"""
        presets = ['none', 'light', 'medium', 'heavy', 'low_quality', 'high_quality']
        
        for preset in presets:
            preprocessor = FramePreprocessor.create_preset(preset)
            assert preprocessor is not None, f"Failed to create preset: {preset}"
            
            config = preprocessor.get_config()
            assert config is not None
            assert 'use_clahe' in config
        
        print(f"\n✅ All {len(presets)} preprocessing presets working")
    
    def test_detector_no_preprocessing_regression(self, high_quality_dataset):
        """
        Test that detector WITHOUT preprocessing still works on high-quality videos
        (Sprint 00/01 regression test)
        """
        detector = SubtitleDetectorV2(show_log=False, preprocessing_preset='none')
        
        videos = high_quality_dataset['videos']
        test_dir = Path('storage/validation/multi_resolution')
        
        results = []
        errors = []
        
        for video_meta in videos[:8]:  # Test subset (2 per resolution)
            video_path = test_dir / video_meta['filename']
            
            if not video_path.exists():
                continue
            
            expected = video_meta['has_subtitles']
            
            has_subs, conf, text, meta = detector.detect_in_video(str(video_path))
            
            correct = (has_subs == expected)
            results.append(correct)
            
            if not correct:
                errors.append({
                    'file': video_meta['filename'],
                    'expected': expected,
                    'detected': has_subs,
                    'confidence': conf
                })
        
        accuracy = (sum(results) / len(results)) * 100 if results else 0
        
        print(f"\n🔍 Regression Test (no preprocessing on high-quality):")
        print(f"   Tested: {len(results)} videos")
        print(f"   Accuracy: {accuracy:.1f}%")
        print(f"   Errors: {len(errors)}")
        
        assert accuracy == 100.0, f"Regression failed! Errors: {errors}"
    
    def test_low_contrast_with_preprocessing(self, low_quality_dataset):
        """Test low-contrast videos WITH preprocessing"""
        detector_no_prep = SubtitleDetectorV2(show_log=False, preprocessing_preset='none')
        detector_with_prep = SubtitleDetectorV2(show_log=False, preprocessing_preset='low_quality')
        
        test_dir = Path('storage/validation/low_quality')
        
        # Get low_contrast videos only
        low_contrast_videos = [v for v in low_quality_dataset['videos'] if v['degradation'] == 'low_contrast']
        
        results_no_prep = []
        results_with_prep = []
        
        for video_meta in low_contrast_videos:
            video_path = test_dir / video_meta['filename']
            expected = video_meta['has_subtitles']
            
            # Test WITHOUT preprocessing
            has_subs_no, _, _, _ = detector_no_prep.detect_in_video(str(video_path))
            results_no_prep.append(has_subs_no == expected)
            
            # Test WITH preprocessing
            has_subs_with, _, _, _ = detector_with_prep.detect_in_video(str(video_path))
            results_with_prep.append(has_subs_with == expected)
        
        acc_no_prep = (sum(results_no_prep) / len(results_no_prep)) * 100
        acc_with_prep = (sum(results_with_prep) / len(results_with_prep)) * 100
        
        print(f"\n🔍 Low-Contrast Videos:")
        print(f"   Without preprocessing: {acc_no_prep:.1f}%")
        print(f"   With preprocessing:    {acc_with_prep:.1f}%")
        print(f"   Improvement:           {acc_with_prep - acc_no_prep:+.1f}%")
        
        # Preprocessing should NOT degrade (maintain or improve)
        assert acc_with_prep >= acc_no_prep, "Preprocessing degraded accuracy!"
    
    def test_compressed_with_preprocessing(self, low_quality_dataset):
        """Test compressed videos WITH preprocessing"""
        detector_with_prep = SubtitleDetectorV2(show_log=False, preprocessing_preset='medium')
        
        test_dir = Path('storage/validation/low_quality')
        
        # Get compressed videos only
        compressed_videos = [v for v in low_quality_dataset['videos'] if v['degradation'] == 'compressed']
        
        results = []
        
        for video_meta in compressed_videos:
            video_path = test_dir / video_meta['filename']
            expected = video_meta['has_subtitles']
            
            has_subs, _, _, _ = detector_with_prep.detect_in_video(str(video_path))
            results.append(has_subs == expected)
        
        accuracy = (sum(results) / len(results)) * 100
        
        print(f"\n🔍 Compressed Videos (with preprocessing):")
        print(f"   Tested: {len(results)} videos")
        print(f"   Accuracy: {accuracy:.1f}%")
        
        # Should handle compressed videos reasonably well
        assert accuracy >= 50.0, "Preprocessing failed on compressed videos"
    
    def test_all_degradations_summary(self, low_quality_dataset):
        """
        Comprehensive test across ALL degradation types
        Compare no preprocessing vs. preprocessing
        """
        detector_no_prep = SubtitleDetectorV2(show_log=False, preprocessing_preset='none')
        detector_with_prep = SubtitleDetectorV2(show_log=False, preprocessing_preset='medium')
        
        test_dir = Path('storage/validation/low_quality')
        videos = low_quality_dataset['videos']
        
        # Group by degradation
        degradations = {}
        
        for video_meta in videos:
            deg = video_meta['degradation']
            if deg not in degradations:
                degradations[deg] = []
            degradations[deg].append(video_meta)
        
        print(f"\n📊 SPRINT 02 COMPREHENSIVE TEST")
        print("=" * 70)
        
        overall_no_prep = []
        overall_with_prep = []
        
        for deg_type, deg_videos in degradations.items():
            results_no_prep = []
            results_with_prep = []
            
            for video_meta in deg_videos:
                video_path = test_dir / video_meta['filename']
                expected = video_meta['has_subtitles']
                
                # Test WITHOUT preprocessing
                has_subs_no, _, _, _ = detector_no_prep.detect_in_video(str(video_path))
                results_no_prep.append(has_subs_no == expected)
                
                # Test WITH preprocessing
                has_subs_with, _, _, _ = detector_with_prep.detect_in_video(str(video_path))
                results_with_prep.append(has_subs_with == expected)
            
            acc_no = (sum(results_no_prep) / len(results_no_prep)) * 100
            acc_with = (sum(results_with_prep) / len(results_with_prep)) * 100
            improvement = acc_with - acc_no
            
            print(f"\n{deg_type:15s} (n={len(deg_videos)}):")
            print(f"  No preprocessing:   {acc_no:5.1f}%")
            print(f"  With preprocessing: {acc_with:5.1f}%")
            print(f"  Improvement:        {improvement:+5.1f}%")
            
            overall_no_prep.extend(results_no_prep)
            overall_with_prep.extend(results_with_prep)
        
        # Overall metrics
        overall_acc_no = (sum(overall_no_prep) / len(overall_no_prep)) * 100
        overall_acc_with = (sum(overall_with_prep) / len(overall_with_prep)) * 100
        overall_improvement = overall_acc_with - overall_acc_no
        
        print(f"\n{'OVERALL':15s} (n={len(videos)}):")
        print(f"  No preprocessing:   {overall_acc_no:5.1f}%")
        print(f"  With preprocessing: {overall_acc_with:5.1f}%")
        print(f"  Improvement:        {overall_improvement:+5.1f}%")
        print("=" * 70)
        
        # Gates
        print(f"\n✅ Gates:")
        print(f"   Preprocessing should NOT degrade: {overall_acc_with >= overall_acc_no}")
        print(f"   Overall accuracy ≥50%:             {overall_acc_with >= 50.0}")
        
        assert overall_acc_with >= overall_acc_no, "Preprocessing degraded overall accuracy!"
        assert overall_acc_with >= 50.0, f"Low overall accuracy: {overall_acc_with:.1f}%"
    
    def test_processing_time_acceptable(self, low_quality_dataset):
        """Test that preprocessing doesn't drastically slow down processing"""
        detector = SubtitleDetectorV2(show_log=False, preprocessing_preset='medium')
        
        test_dir = Path('storage/validation/low_quality')
        
        # Test on a few videos
        test_videos = low_quality_dataset['videos'][:4]
        
        times = []
        
        for video_meta in test_videos:
            video_path = test_dir / video_meta['filename']
            
            start = time.time()
            detector.detect_in_video(str(video_path))
            elapsed = time.time() - start
            
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        max_time = max(times)
        
        print(f"\n⏱️  Processing Time (with preprocessing):")
        print(f"   Average: {avg_time:.2f}s")
        print(f"   Max:     {max_time:.2f}s")
        print(f"   Target:  <10s per video")
        
        assert max_time < 10.0, f"Processing too slow: {max_time:.2f}s"
    
    def test_maintains_high_quality_accuracy(self, high_quality_dataset):
        """
        Test that preprocessing MAINTAINS 100% accuracy on high-quality videos
        (Critical: preprocessing should not hurt clean videos)
        """
        detector = SubtitleDetectorV2(show_log=False, preprocessing_preset='medium')
        
        test_dir = Path('storage/validation/multi_resolution')
        videos = high_quality_dataset['videos']
        
        results = []
        errors = []
        
        for video_meta in videos:
            video_path = test_dir / video_meta['filename']
            expected = video_meta['has_subtitles']
            
            has_subs, conf, _, _ = detector.detect_in_video(str(video_path))
            
            correct = (has_subs == expected)
            results.append(correct)
            
            if not correct:
                errors.append({
                    'file': video_meta['filename'],
                    'resolution': video_meta['resolution'],
                    'expected': expected,
                    'detected': has_subs,
                    'confidence': conf
                })
        
        accuracy = (sum(results) / len(results)) * 100
        
        print(f"\n🔍 High-Quality Videos WITH Preprocessing:")
        print(f"   Tested: {len(results)} videos (all resolutions)")
        print(f"   Accuracy: {accuracy:.1f}%")
        print(f"   Errors: {len(errors)}")
        
        if errors:
            print(f"   Error details: {errors[:3]}")
        
        # CRITICAL: Must maintain 100% on high-quality videos
        assert accuracy == 100.0, f"Preprocessing degraded high-quality accuracy! Errors: {errors}"


if __name__ == "__main__":
    pytest.main([__file__, '-v', '--tb=short'])
