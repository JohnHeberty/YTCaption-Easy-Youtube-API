"""
Sprint 01 Pytest - Multi-Resolution Subtitle Detection

Tests dynamic resolution support:
- 720p, 1080p, 1440p, 4K
- ROI adaptation per resolution
- Temporal sampling across resolutions
- 100% accuracy target

Based on SubtitleDetectorV2 (simple, reliable approach)
"""
import pytest
import cv2
from pathlib import Path
import json
from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2


@pytest.fixture(scope="module")
def detector():
    """Initialize SubtitleDetectorV2 once for all tests"""
    return SubtitleDetectorV2(show_log=False)


@pytest.fixture(scope="module")
def multi_resolution_dataset():
    """Load multi-resolution dataset ground truth"""
    dataset_dir = Path('storage/validation/multi_resolution')
    ground_truth_path = dataset_dir / 'ground_truth.json'
    
    with open(ground_truth_path, 'r') as f:
        data = json.load(f)
    
    return dataset_dir, data


class TestSprint01Resolution:
    """Sprint 01: Dynamic Resolution Support Tests"""
    
    def test_720p_detection(self, detector, multi_resolution_dataset):
        """Test: Detect subtitles in 720p videos"""
        dataset_dir, data = multi_resolution_dataset
        
        videos_720p = [v for v in data['videos'] if v['resolution'] == '720p']
        
        tp, tn, fp, fn = 0, 0, 0, 0
        
        for video in videos_720p:
            video_path = str(dataset_dir / video['filename'])
            expected = video['has_subtitles']
            
            has_subs, conf, text, meta = detector.detect_in_video(video_path)
            
            assert meta['resolution'] == (1280, 720), f"Resolution mismatch for {video['filename']}"
            
            if has_subs and expected:
                tp += 1
            elif not has_subs and not expected:
                tn += 1
            elif has_subs and not expected:
                fp += 1
            else:
                fn += 1
        
        accuracy = (tp + tn) / len(videos_720p)
        assert accuracy == 1.0, f"720p accuracy {accuracy:.2%} < 100% (TP={tp}, TN={tn}, FP={fp}, FN={fn})"
    
    def test_1080p_detection(self, detector, multi_resolution_dataset):
        """Test: Detect subtitles in 1080p videos"""
        dataset_dir, data = multi_resolution_dataset
        
        videos_1080p = [v for v in data['videos'] if v['resolution'] == '1080p']
        
        tp, tn, fp, fn = 0, 0, 0, 0
        
        for video in videos_1080p:
            video_path = str(dataset_dir / video['filename'])
            expected = video['has_subtitles']
            
            has_subs, conf, text, meta = detector.detect_in_video(video_path)
            
            assert meta['resolution'] == (1920, 1080), f"Resolution mismatch for {video['filename']}"
            
            if has_subs and expected:
                tp += 1
            elif not has_subs and not expected:
                tn += 1
            elif has_subs and not expected:
                fp += 1
            else:
                fn += 1
        
        accuracy = (tp + tn) / len(videos_1080p)
        assert accuracy == 1.0, f"1080p accuracy {accuracy:.2%} < 100% (TP={tp}, TN={tn}, FP={fp}, FN={fn})"
    
    def test_1440p_detection(self, detector, multi_resolution_dataset):
        """Test: Detect subtitles in 1440p videos"""
        dataset_dir, data = multi_resolution_dataset
        
        videos_1440p = [v for v in data['videos'] if v['resolution'] == '1440p']
        
        tp, tn, fp, fn = 0, 0, 0, 0
        
        for video in videos_1440p:
            video_path = str(dataset_dir / video['filename'])
            expected = video['has_subtitles']
            
            has_subs, conf, text, meta = detector.detect_in_video(video_path)
            
            assert meta['resolution'] == (2560, 1440), f"Resolution mismatch for {video['filename']}"
            
            if has_subs and expected:
                tp += 1
            elif not has_subs and not expected:
                tn += 1
            elif has_subs and not expected:
                fp += 1
            else:
                fn += 1
        
        accuracy = (tp + tn) / len(videos_1440p)
        assert accuracy == 1.0, f"1440p accuracy {accuracy:.2%} < 100% (TP={tp}, TN={tn}, FP={fp}, FN={fn})"
    
    def test_4k_detection(self, detector, multi_resolution_dataset):
        """Test: Detect subtitles in 4K videos"""
        dataset_dir, data = multi_resolution_dataset
        
        videos_4k = [v for v in data['videos'] if v['resolution'] == '4K']
        
        tp, tn, fp, fn = 0, 0, 0, 0
        
        for video in videos_4k:
            video_path = str(dataset_dir / video['filename'])
            expected = video['has_subtitles']
            
            has_subs, conf, text, meta = detector.detect_in_video(video_path)
            
            assert meta['resolution'] == (3840, 2160), f"Resolution mismatch for {video['filename']}"
            
            if has_subs and expected:
                tp += 1
            elif not has_subs and not expected:
                tn += 1
            elif has_subs and not expected:
                fp += 1
            else:
                fn += 1
        
        accuracy = (tp + tn) / len(videos_4k)
        assert accuracy == 1.0, f"4K accuracy {accuracy:.2%} < 100% (TP={tp}, TN={tn}, FP={fp}, FN={fn})"
    
    def test_roi_adaptation(self, detector, multi_resolution_dataset):
        """Test: ROI adapts correctly to each resolution"""
        dataset_dir, data = multi_resolution_dataset
        
        # Test ROI calculation for each resolution
        expected_rois = {
            (1280, 720): (1280, 180),    # 25% of 720
            (1920, 1080): (1920, 270),   # 25% of 1080
            (2560, 1440): (2560, 360),   # 25% of 1440
            (3840, 2160): (3840, 540)    # 25% of 2160
        }
        
        for video in data['videos']:
            video_path = str(dataset_dir / video['filename'])
            width, height, duration = detector.detect_resolution(video_path)
            resolution = (width, height)
            
            # Extract a frame
            frame = detector.extract_frame_at_timestamp(video_path, 1.0)
            assert frame is not None, f"Failed to extract frame from {video['filename']}"
            
            # Get ROI
            roi_frame, roi_meta = detector.get_roi_for_resolution(frame, resolution)
            
            # Check ROI size
            expected_roi_size = expected_rois[resolution]
            assert roi_meta['roi_size'] == expected_roi_size, (
                f"ROI size mismatch for {resolution}: "
                f"expected {expected_roi_size}, got {roi_meta['roi_size']}"
            )
            
            # Check ROI percentage
            assert roi_meta['roi_percentage'] == 0.25, "ROI should be 25% of frame height"
    
    def test_temporal_sampling(self, detector):
        """Test: Temporal sampling generates correct timestamps"""
        # Test various durations
        test_cases = [
            (3.0, 6),   # 3s video, 6 samples
            (10.0, 6),  # 10s video, 6 samples
            (30.0, 6),  # 30s video, 6 samples
        ]
        
        for duration, num_samples in test_cases:
            timestamps = detector.sample_temporal_frames(duration, num_samples)
            
            # Check count
            assert len(timestamps) <= num_samples, f"Too many timestamps: {len(timestamps)} > {num_samples}"
            
            # Check range
            for ts in timestamps:
                assert 0 <= ts < duration, f"Timestamp {ts} out of range [0, {duration})"
            
            # Check sorted
            assert timestamps == sorted(timestamps), "Timestamps should be sorted"
            
            # Check includes start
            assert timestamps[0] == 0.0, "First timestamp should be 0.0"
    
    def test_mixed_resolution_f1_target(self, detector, multi_resolution_dataset):
        """Test: F1 ≥90% on full mixed-resolution dataset"""
        dataset_dir, data = multi_resolution_dataset
        
        tp, tn, fp, fn = 0, 0, 0, 0
        
        for video in data['videos']:
            video_path = str(dataset_dir / video['filename'])
            expected = video['has_subtitles']
            
            has_subs, conf, text, meta = detector.detect_in_video(video_path)
            
            if has_subs and expected:
                tp += 1
            elif not has_subs and not expected:
                tn += 1
            elif has_subs and not expected:
                fp += 1
            else:
                fn += 1
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        assert f1 >= 0.90, f"F1 Score {f1:.2%} < 90% target (TP={tp}, TN={tn}, FP={fp}, FN={fn})"
    
    def test_all_metrics_summary(self, detector, multi_resolution_dataset):
        """Comprehensive test: Measure all baseline metrics across resolutions"""
        dataset_dir, data = multi_resolution_dataset
        
        tp, tn, fp, fn = 0, 0, 0, 0
        results_by_resolution = {}
        
        for video in data['videos']:
            video_path = str(dataset_dir / video['filename'])
            expected = video['has_subtitles']
            resolution_name = video['resolution']
            
            has_subs, conf, text, meta = detector.detect_in_video(video_path)
            
            # Track overall
            if has_subs and expected:
                tp += 1
            elif not has_subs and not expected:
                tn += 1
            elif has_subs and not expected:
                fp += 1
            else:
                fn += 1
            
            # Track by resolution
            if resolution_name not in results_by_resolution:
                results_by_resolution[resolution_name] = {'tp': 0, 'tn': 0, 'fp': 0, 'fn': 0}
            
            if has_subs and expected:
                results_by_resolution[resolution_name]['tp'] += 1
            elif not has_subs and not expected:
                results_by_resolution[resolution_name]['tn'] += 1
            elif has_subs and not expected:
                results_by_resolution[resolution_name]['fp'] += 1
            else:
                results_by_resolution[resolution_name]['fn'] += 1
        
        # Calculate metrics
        accuracy = (tp + tn) / (tp + tn + fp + fn)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        # Print summary
        print("\n" + "=" * 70)
        print("📊 SPRINT 01 MULTI-RESOLUTION RESULTS")
        print("=" * 70)
        print(f"Confusion Matrix:")
        print(f"  TP: {tp:2}/8 WITH subtitles")
        print(f"  TN: {tn:2}/8 WITHOUT subtitles")
        print(f"  FP: {fp:2}")
        print(f"  FN: {fn:2}")
        print(f"\nMetrics:")
        print(f"  Accuracy:    {accuracy*100:.1f}%")
        print(f"  Precision:   {precision*100:.1f}%")
        print(f"  Recall:      {recall*100:.1f}%")
        print(f"  FPR:         {fpr*100:.1f}%")
        print(f"  F1 Score:    {f1*100:.1f}%")
        print(f"\nGates (Sprint 01):")
        print(f"  Recall ≥90%: {recall*100:.1f}% {'✅ PASS' if recall >= 0.90 else '❌ FAIL'}")
        print(f"  F1 ≥90%:     {f1*100:.1f}% {'✅ PASS' if f1 >= 0.90 else '❌ FAIL'}")
        print(f"  FPR ≤5%:     {fpr*100:.1f}% {'✅ PASS' if fpr <= 0.05 else '❌ FAIL'}")
        
        print(f"\nPer-Resolution Accuracy:")
        for res in ['720p', '1080p', '1440p', '4K']:
            if res in results_by_resolution:
                r = results_by_resolution[res]
                res_acc = (r['tp'] + r['tn']) / (r['tp'] + r['tn'] + r['fp'] + r['fn'])
                print(f"  {res}: {res_acc*100:.0f}%")
        
        print("=" * 70)
        
        # Assert gates
        assert recall >= 0.90, f"Recall gate failed: {recall:.2%} < 90%"
        assert f1 >= 0.90, f"F1 gate failed: {f1:.2%} < 90%"
        assert fpr <= 0.05, f"FPR gate failed: {fpr:.2%} > 5%"
