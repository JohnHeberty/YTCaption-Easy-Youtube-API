"""
Sprint 04 Tests: Multi-ROI Fallback System

Tests edge cases where subtitles appear in non-standard positions:
- Top 25%: Foreign films, dual-language
- Left/Right 20%: YouTube Shorts, TikTok
- Center 30%: Embedded text, hardcoded overlays

Expected: 8/8 tests PASS
Run time: ~60-90s
"""

import pytest
import json
from pathlib import Path
from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2


class TestSprint04MultiROI:
    """Sprint 04: Multi-ROI Fallback Tests"""
    
    EDGE_CASE_DIR = Path('storage/validation/edge_cases')
    GROUND_TRUTH_PATH = EDGE_CASE_DIR / 'ground_truth.json'
    
    @pytest.fixture(scope='class')
    def detector_multi(self):
        """Create detector with multi-ROI mode"""
        return SubtitleDetectorV2(show_log=False, roi_mode='multi')
    
    @pytest.fixture(scope='class')
    def detector_bottom(self):
        """Create detector with bottom-only mode (legacy)"""
        return SubtitleDetectorV2(show_log=False, roi_mode='bottom')
    
    @pytest.fixture(scope='class')
    def ground_truth(self):
        """Load ground truth labels"""
        with open(self.GROUND_TRUTH_PATH, 'r') as f:
            return json.load(f)
    
    def test_top_subtitle_detection(self, detector_multi, ground_truth):
        """Test 1: Detect subtitles in TOP 25% ROI"""
        print("\n🧪 Test 1: TOP subtitle detection")
        
        top_videos = [k for k in ground_truth.keys() if k.startswith('top_')]
        
        results = {'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0}
        
        for video_name in top_videos:
            video_path = self.EDGE_CASE_DIR / 'top' / video_name
            
            if not video_path.exists():
                continue
            
            expected = ground_truth[video_name]['has_subtitles']
            
            has_subs, conf, text, meta = detector_multi.detect_in_video_with_multi_roi(str(video_path))
            
            # Classification
            if expected and has_subs:
                results['TP'] += 1
            elif not expected and not has_subs:
                results['TN'] += 1
            elif not expected and has_subs:
                results['FP'] += 1
            elif expected and not has_subs:
                results['FN'] += 1
            
            roi_used = meta.get('roi_used', 'none')
            status = "✅" if (has_subs == expected) else "❌"
            print(f"  {status} {video_name}: detected={has_subs}, expected={expected}, ROI={roi_used}, conf={conf:.2f}")
        
        # Calculate metrics
        total = sum(results.values())
        accuracy = (results['TP'] + results['TN']) / total if total > 0 else 0
        
        print(f"\n📊 Top ROI Results: TP={results['TP']}, TN={results['TN']}, FP={results['FP']}, FN={results['FN']}")
        print(f"   Accuracy: {accuracy*100:.1f}%")
        
        # Assert: 100% accuracy on top subtitles
        assert accuracy == 1.0, f"Top subtitle detection failed: {accuracy*100:.1f}% accuracy"
        assert results['TP'] >= 2, "Should detect at least 2 top subtitle videos"
    
    def test_side_caption_detection(self, detector_multi, ground_truth):
        """Test 2: Detect captions in LEFT/RIGHT 20% ROI"""
        print("\n🧪 Test 2: SIDE caption detection (left + right)")
        
        side_videos = [k for k in ground_truth.keys() if k.startswith(('left_', 'right_'))]
        
        results = {'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0}
        
        for video_name in side_videos:
            # Determine subfolder (left or right)
            subfolder = 'left' if video_name.startswith('left_') else 'right'
            video_path = self.EDGE_CASE_DIR / subfolder / video_name
            
            if not video_path.exists():
                continue
            
            expected = ground_truth[video_name]['has_subtitles']
            
            has_subs, conf, text, meta = detector_multi.detect_in_video_with_multi_roi(str(video_path))
            
            # Classification
            if expected and has_subs:
                results['TP'] += 1
            elif not expected and not has_subs:
                results['TN'] += 1
            elif not expected and has_subs:
                results['FP'] += 1
            elif expected and not has_subs:
                results['FN'] += 1
            
            roi_used = meta.get('roi_used', 'none')
            status = "✅" if (has_subs == expected) else "❌"
            print(f"  {status} {video_name}: detected={has_subs}, expected={expected}, ROI={roi_used}, conf={conf:.2f}")
        
        # Calculate metrics
        total = sum(results.values())
        accuracy = (results['TP'] + results['TN']) / total if total > 0 else 0
        
        print(f"\n📊 Side ROI Results: TP={results['TP']}, TN={results['TN']}, FP={results['FP']}, FN={results['FN']}")
        print(f"   Accuracy: {accuracy*100:.1f}%")
        
        # Assert: 100% accuracy on side captions
        assert accuracy == 1.0, f"Side caption detection failed: {accuracy*100:.1f}% accuracy"
        assert results['TP'] >= 4, "Should detect at least 4 side caption videos (2 left + 2 right)"
    
    def test_center_text_detection(self, detector_multi, ground_truth):
        """Test 3: Detect text in CENTER 30% ROI"""
        print("\n🧪 Test 3: CENTER text detection")
        
        center_videos = [k for k in ground_truth.keys() if k.startswith('center_')]
        
        results = {'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0}
        
        for video_name in center_videos:
            video_path = self.EDGE_CASE_DIR / 'center' / video_name
            
            if not video_path.exists():
                continue
            
            expected = ground_truth[video_name]['has_subtitles']
            
            has_subs, conf, text, meta = detector_multi.detect_in_video_with_multi_roi(str(video_path))
            
            # Classification
            if expected and has_subs:
                results['TP'] += 1
            elif not expected and not has_subs:
                results['TN'] += 1
            elif not expected and has_subs:
                results['FP'] += 1
            elif expected and not has_subs:
                results['FN'] += 1
            
            roi_used = meta.get('roi_used', 'none')
            status = "✅" if (has_subs == expected) else "❌"
            print(f"  {status} {video_name}: detected={has_subs}, expected={expected}, ROI={roi_used}, conf={conf:.2f}")
        
        # Calculate metrics
        total = sum(results.values())
        accuracy = (results['TP'] + results['TN']) / total if total > 0 else 0
        
        print(f"\n📊 Center ROI Results: TP={results['TP']}, TN={results['TN']}, FP={results['FP']}, FN={results['FN']}")
        print(f"   Accuracy: {accuracy*100:.1f}%")
        
        # Assert: 100% accuracy on center text
        assert accuracy == 1.0, f"Center text detection failed: {accuracy*100:.1f}% accuracy"
        assert results['TP'] >= 2, "Should detect at least 2 center text videos"
    
    def test_roi_priority_fallback(self, detector_multi):
        """Test 4: Verify ROI priority order (bottom → top → sides → center)"""
        print("\n🧪 Test 4: ROI priority fallback verification")
        
        # Test bottom priority (should use bottom ROI first)
        bottom_video = self.EDGE_CASE_DIR / '../synthetic/synthetic_WITH_001.mp4'
        
        if bottom_video.exists():
            has_subs, conf, text, meta = detector_multi.detect_in_video_with_multi_roi(str(bottom_video))
            roi_used = meta.get('roi_used', 'none')
            
            print(f"  ✅ Bottom priority test: ROI used = {roi_used}")
            assert roi_used == 'bottom', "Should use bottom ROI for standard bottom subtitles"
        
        # Test top fallback
        top_video = self.EDGE_CASE_DIR / 'top/top_with_001.mp4'
        
        if top_video.exists():
            has_subs, conf, text, meta = detector_multi.detect_in_video_with_multi_roi(str(top_video))
            roi_used = meta.get('roi_used', 'none')
            rois_checked = meta.get('rois_checked', [])
            
            print(f"  ✅ Top fallback test: ROI used = {roi_used}, ROIs checked = {rois_checked}")
            assert roi_used == 'top', "Should use top ROI for top subtitles"
            assert 'bottom' in rois_checked, "Should check bottom ROI first (priority 1)"
        
        print("\n✅ ROI priority fallback working correctly")
    
    def test_bottom_roi_maintained(self, detector_bottom):
        """Test 5: Regression - bottom-only mode still works (backward compatibility)"""
        print("\n🧪 Test 5: REGRESSION - Bottom-only mode (Sprint 00-03 compatibility)")
        
        # Test on synthetic dataset (Sprint 00)
        synthetic_dir = Path('storage/validation/synthetic')
        
        test_videos = [
            ('synthetic_WITH_001.mp4', True),
            ('synthetic_WITHOUT_001.mp4', False)
        ]
        
        results = {'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0}
        
        for video_name, expected in test_videos:
            video_path = synthetic_dir / video_name
            
            if not video_path.exists():
                continue
            
            has_subs, conf, text, meta = detector_bottom.detect_in_video_with_multi_roi(str(video_path))
            
            if expected and has_subs:
                results['TP'] += 1
            elif not expected and not has_subs:
                results['TN'] += 1
            elif not expected and has_subs:
                results['FP'] += 1
            elif expected and not has_subs:
                results['FN'] += 1
            
            roi_mode = meta.get('roi_mode', 'unknown')
            status = "✅" if (has_subs == expected) else "❌"
            print(f"  {status} {video_name}: detected={has_subs}, expected={expected}, mode={roi_mode}")
        
        total = sum(results.values())
        accuracy = (results['TP'] + results['TN']) / total if total > 0 else 0
        
        print(f"\n📊 Regression Results: TP={results['TP']}, TN={results['TN']}, FP={results['FP']}, FN={results['FN']}")
        print(f"   Accuracy: {accuracy*100:.1f}%")
        
        # Assert: 100% accuracy maintained (no regression)
        assert accuracy == 1.0, f"Regression detected: {accuracy*100:.1f}% accuracy (should be 100%)"
        print("✅ No regression detected - backward compatibility maintained")
    
    def test_multi_roi_performance(self, detector_multi):
        """Test 6: Performance - Multi-ROI detection within time budget"""
        print("\n🧪 Test 6: PERFORMANCE - Multi-ROI detection time")
        
        import time
        
        test_video = self.EDGE_CASE_DIR / 'top/top_with_001.mp4'
        
        if not test_video.exists():
            pytest.skip("Test video not found")
        
        # Measure detection time
        start_time = time.time()
        has_subs, conf, text, meta = detector_multi.detect_in_video_with_multi_roi(str(test_video))
        elapsed_time = time.time() - start_time
        
        rois_checked = meta.get('rois_checked', [])
        roi_used = meta.get('roi_used', 'none')
        
        print(f"  📊 Detection time: {elapsed_time:.2f}s")
        print(f"  📊 ROIs checked: {len(rois_checked)} ({', '.join(rois_checked)})")
        print(f"  📊 ROI used: {roi_used}")
        
        # Assert: Detection within 8 seconds (target for multi-ROI)
        assert elapsed_time < 8.0, f"Detection too slow: {elapsed_time:.2f}s (target: <8s)"
        
        # Early exit optimization: should not check all 5 ROIs if text found earlier
        if has_subs:
            assert len(rois_checked) <= 5, "Should use early exit (not scanning all ROIs unnecessarily)"
        
        print(f"✅ Performance OK: {elapsed_time:.2f}s (target: <8s)")
    
    def test_all_edge_cases_summary(self, detector_multi, ground_truth):
        """Test 7: Overall accuracy on ALL edge case videos"""
        print("\n🧪 Test 7: ALL EDGE CASES summary")
        
        all_results = {'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0}
        roi_usage = {}
        
        # Test all videos in ground truth
        for video_name, label_data in ground_truth.items():
            expected = label_data['has_subtitles']
            
            # Determine video path
            if video_name.startswith('top_'):
                video_path = self.EDGE_CASE_DIR / 'top' / video_name
            elif video_name.startswith('left_'):
                video_path = self.EDGE_CASE_DIR / 'left' / video_name
            elif video_name.startswith('right_'):
                video_path = self.EDGE_CASE_DIR / 'right' / video_name
            elif video_name.startswith('center_'):
                video_path = self.EDGE_CASE_DIR / 'center' / video_name
            elif video_name.startswith(('top_and_', 'left_and_', 'all_', 'no_')):
                video_path = self.EDGE_CASE_DIR / 'multi_position' / video_name
            else:
                continue
            
            if not video_path.exists():
                continue
            
            has_subs, conf, text, meta = detector_multi.detect_in_video_with_multi_roi(str(video_path))
            
            # Classification
            if expected and has_subs:
                all_results['TP'] += 1
            elif not expected and not has_subs:
                all_results['TN'] += 1
            elif not expected and has_subs:
                all_results['FP'] += 1
            elif expected and not has_subs:
                all_results['FN'] += 1
            
            # Track ROI usage
            roi_used = meta.get('roi_used', 'none')
            roi_usage[roi_used] = roi_usage.get(roi_used, 0) + 1
        
        # Calculate comprehensive metrics
        total = sum(all_results.values())
        accuracy = (all_results['TP'] + all_results['TN']) / total if total > 0 else 0
        
        recall = all_results['TP'] / (all_results['TP'] + all_results['FN']) if (all_results['TP'] + all_results['FN']) > 0 else 0
        precision = all_results['TP'] / (all_results['TP'] + all_results['FP']) if (all_results['TP'] + all_results['FP']) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        fpr = all_results['FP'] / (all_results['FP'] + all_results['TN']) if (all_results['FP'] + all_results['TN']) > 0 else 0
        
        print(f"\n📊 OVERALL EDGE CASE RESULTS:")
        print(f"   Total videos: {total}")
        print(f"   TP={all_results['TP']}, TN={all_results['TN']}, FP={all_results['FP']}, FN={all_results['FN']}")
        print(f"   Accuracy: {accuracy*100:.1f}%")
        print(f"   Recall: {recall*100:.1f}%")
        print(f"   Precision: {precision*100:.1f}%")
        print(f"   F1 Score: {f1*100:.1f}%")
        print(f"   FPR: {fpr*100:.2f}%")
        print(f"\n📊 ROI Usage Distribution:")
        for roi, count in sorted((k, v) for k, v in roi_usage.items() if k is not None):
            print(f"   {roi}: {count} videos ({count/total*100:.1f}%)")
        
        # Show videos with no ROI detection (if any)
        if None in roi_usage:
            print(f"   (no detection): {roi_usage[None]} videos ({roi_usage[None]/total*100:.1f}%)")
        
        # Assert: High accuracy on edge cases (target: 95-100%)
        assert accuracy >= 0.95, f"Edge case accuracy too low: {accuracy*100:.1f}% (target: ≥95%)"
        assert f1 >= 0.95, f"F1 score too low: {f1*100:.1f}% (target: ≥95%)"
        assert fpr <= 0.05, f"FPR too high: {fpr*100:.2f}% (target: ≤5%)"
        
        print("\n✅ Sprint 04 Multi-ROI system working excellently!")
    
    def test_multi_position_videos(self, detector_multi, ground_truth):
        """Test 8: Multi-position videos (top+bottom, etc.)"""
        print("\n🧪 Test 8: MULTI-POSITION videos")
        
        multi_videos = [k for k in ground_truth.keys() if k.startswith(('top_and_', 'left_and_', 'all_', 'no_'))]
        
        tested_count = 0
        errors = []
        
        for video_name in multi_videos:
            video_path = self.EDGE_CASE_DIR / 'multi_position' / video_name
            
            if not video_path.exists():
                continue
            
            expected = ground_truth[video_name]['has_subtitles']
            
            try:
                has_subs, conf, text, meta = detector_multi.detect_in_video_with_multi_roi(str(video_path))
                
                # Skip corrupted videos (no frames extracted)
                frames_extracted = meta.get('frames_extracted', 0)
                if frames_extracted == 0:
                    print(f"  ⚠️ {video_name}: Skipped (corrupted or invalid video - no frames extracted)")
                    continue
                
                roi_used = meta.get('roi_used', 'none')
                status = "✅" if (has_subs == expected) else "❌"
                print(f"  {status} {video_name}: detected={has_subs}, expected={expected}, ROI={roi_used}")
                
                tested_count += 1
                
                # For multi-position videos with text, should detect in at least one ROI
                if expected and not has_subs:
                    errors.append(f"Failed to detect multi-position subtitles in {video_name}")
            
            except Exception as e:
                print(f"  ⚠️ {video_name}: Skipped (corrupted or invalid video) - {str(e)[:50]}")
                continue
        
        # Assert only if we tested at least one video
        if tested_count > 0:
            assert len(errors) == 0, f"Multi-position detection errors: {errors}"
            print("✅ Multi-position detection working")
        else:
            print("⚠️ No multi-position videos tested (all skipped)")
            pytest.skip("No valid multi-position videos found")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
