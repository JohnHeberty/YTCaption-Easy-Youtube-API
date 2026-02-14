#!/usr/bin/env python3
"""
Validation Test - Verify fixes are working
Tests that PaddleOCR can detect subtitles with new thresholds
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_detection():
    """Test detection with new thresholds"""
    from app.video_processing.ocr_detector import OCRDetector
    import cv2
    
    print("="*80)
    print("🧪 VALIDATION TEST - Verifying Fixes")
    print("="*80)
    print()
    
    # Initialize detector
    print("🚀 Initializing PaddleOCR...")
    detector = OCRDetector()
    print("✅ Detector initialized\n")
    
    base_dir = Path(__file__).parent / "storage" / "validation" / "sample_NOT_OK"
    
    # Test H.264 videos (should detect with threshold 30%)
    h264_videos = [
        "07EbeE3BRIw.mp4",
        "5KgYaiBd6oY.mp4",
        "TR_YdL6D30k_h264.mp4"  # Converted AV1
    ]
    
    results = []
    
    for video_name in h264_videos:
        video_path = base_dir / video_name
        if not video_path.exists():
            print(f"⚠️  Skipping: {video_name} (not found)")
            continue
        
        print(f"📹 Testing: {video_name}")
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"  ❌ Cannot open video")
            results.append((video_name, "FAIL", "Cannot open"))
            continue
        
        # Sample 5 frames
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        sample_interval = max(1, int(fps * 2))
        
        positive_frames = 0
        total_samples = 0
        
        for i in range(5):
            frame_idx = i * sample_interval
            if frame_idx >= total_frames:
                break
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if not ret:
                break
            
            # Test with threshold 30% (should work now!)
            result = detector.detect_subtitle_in_frame(frame, min_confidence=30)
            
            total_samples += 1
            if result.has_subtitle:
                positive_frames += 1
        
        cap.release()
        
        detection_rate = (positive_frames / total_samples * 100) if total_samples > 0 else 0
        
        # Success if >50% frames detected
        if detection_rate >= 50:
            print(f"  ✅ SUCCESS: {positive_frames}/{total_samples} frames ({detection_rate:.0f}%)")
            results.append((video_name, "PASS", f"{detection_rate:.0f}%"))
        else:
            print(f"  ❌ FAIL: {positive_frames}/{total_samples} frames ({detection_rate:.0f}%)")
            results.append((video_name, "FAIL", f"{detection_rate:.0f}%"))
        
        print()
    
    # Summary
    print("="*80)
    print("📊 VALIDATION SUMMARY")
    print("="*80)
    print()
    
    passed = sum(1 for _, status, _ in results if status == "PASS")
    total = len(results)
    
    for video, status, rate in results:
        emoji = "✅" if status == "PASS" else "❌"
        print(f"  {emoji} {video}: {rate}")
    
    print()
    print(f"Result: {passed}/{total} tests passed")
    print()
    
    if passed >= 2:  # At least 2 of 3 should pass
        print("✅ VALIDATION PASSED - Fixes are working!")
        print()
        return 0
    else:
        print("❌ VALIDATION FAILED - Need more investigation")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(test_detection())
