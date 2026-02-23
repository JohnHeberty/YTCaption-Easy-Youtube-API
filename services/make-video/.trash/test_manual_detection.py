#!/usr/bin/env python3
"""
Manual test to debug why OCR is not detecting subtitles
"""

import sys
import cv2
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))
from app.video_processing.ocr_detector import OCRDetector

def test_video(video_path: str):
    """Test OCR detection on a video"""
    
    print(f"\n{'='*80}")
    print(f"Testing: {Path(video_path).name}")
    print(f"{'='*80}\n")
    
    # Initialize detector
    print("🚀 Initializing PaddleOCR...")
    detector = OCRDetector()
    print("✅ Detector initialized\n")
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Failed to open video: {video_path}")
        return
    
    # Get video info
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps if fps > 0 else 0
    
    print(f"📹 Video Info:")
    print(f"   Frames: {total_frames}")
    print(f"   FPS: {fps:.2f}")
    print(f"   Duration: {duration:.2f}s\n")
    
    # Test with different confidence thresholds
    thresholds = [30, 40, 50, 60, 70, 80]
    
    # Sample 10 frames
    sample_interval = max(1, int(fps * 2))  # Every 2 seconds
    max_samples = min(10, total_frames // sample_interval)
    frame_indices = list(range(0, total_frames, sample_interval))[:max_samples]
    
    print(f"🔍 Testing {len(frame_indices)} frames with different thresholds...\n")
    
    results_by_threshold = {t: {"positive": 0, "total": 0} for t in thresholds}
    
    for frame_idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        
        if not ret:
            continue
        
        frame_time = frame_idx / fps if fps > 0 else 0
        print(f"Frame {frame_idx} (t={frame_time:.1f}s):")
        
        for threshold in thresholds:
            result = detector.detect_subtitle_in_frame(frame, min_confidence=threshold)
            results_by_threshold[threshold]["total"] += 1
            
            if result.has_subtitle:
                results_by_threshold[threshold]["positive"] += 1
                print(f"  ✅ threshold={threshold}: DETECTED (conf={result.confidence:.2f}) - words: {result.readable_words[:3]}")
            else:
                print(f"  ❌ threshold={threshold}: NOT DETECTED")
        
        print()
    
    cap.release()
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 SUMMARY BY THRESHOLD")
    print(f"{'='*80}\n")
    
    for threshold in thresholds:
        data = results_by_threshold[threshold]
        positive = data["positive"]
        total = data["total"]
        percentage = (positive / total * 100) if total > 0 else 0
        
        # Classification logic: >30% = has subtitle
        classification = "✅ HAS SUBTITLE" if percentage > 30 else "❌ NO SUBTITLE"
        
        print(f"Threshold {threshold:2d}: {positive:2d}/{total:2d} frames ({percentage:5.1f}%) → {classification}")
    
    print()

if __name__ == "__main__":
    # Test a few videos
    base_dir = Path(__file__).parent / "storage" / "validation"
    
    print("\n" + "="*80)
    print("🧪 MANUAL OCR DETECTION TEST")
    print("="*80)
    
    # Test NOT_OK videos (should have subtitles)
    not_ok_videos = list((base_dir / "sample_NOT_OK").glob("*.mp4"))[:3]
    
    print(f"\nTesting {len(not_ok_videos)} NOT_OK videos (should detect subtitles):\n")
    
    for video in not_ok_videos:
        test_video(str(video))
        print("\n" + "-"*80 + "\n")
    
    # Test OK videos (should NOT have subtitles)
    ok_videos = list((base_dir / "sample_OK").glob("*.mp4"))[:2]
    
    print(f"\nTesting {len(ok_videos)} OK videos (should NOT detect subtitles):\n")
    
    for video in ok_videos:
        test_video(str(video))
        print("\n" + "-"*80 + "\n")
    
    print("\n✅ Test complete!")
