"""
Sprint 01 Baseline - Multi-Resolution Test

Test SubtitleDetectorV2 on all resolutions:
- 720p, 1080p, 1440p, 4K
- 8 WITH + 8 WITHOUT = 16 videos
- Target: 100% accuracy across all resolutions
"""
import json
from pathlib import Path
from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2


def run_multi_resolution_baseline():
    """Run baseline test on multi-resolution dataset"""
    
    print("📊 SPRINT 01 BASELINE - Multi-Resolution Test")
    print("=" * 70)
    
    detector = SubtitleDetectorV2(show_log=False)
    
    # Load ground truth
    dataset_dir = Path('storage/validation/multi_resolution')
    ground_truth_path = dataset_dir / 'ground_truth.json'
    
    with open(ground_truth_path, 'r') as f:
        ground_truth = json.load(f)
    
    print(f"\n📂 Dataset: {ground_truth['dataset_info']['name']}")
    print(f"   Total videos: {ground_truth['dataset_info']['total_videos']}")
    print(f"   Resolutions: {', '.join(ground_truth['dataset_info']['resolutions'])}")
    print(f"   Positive/Negative: {ground_truth['dataset_info']['positive_samples']}/{ground_truth['dataset_info']['negative_samples']}")
    
    # Test all videos
    tp, tn, fp, fn = 0, 0, 0, 0
    results_by_resolution = {}
    
    print(f"\n🎬 Testing {len(ground_truth['videos'])} videos...")
    print()
    
    for idx, video_data in enumerate(ground_truth['videos'], 1):
        video_path = str(dataset_dir / video_data['filename'])
        expected = video_data['has_subtitles']
        resolution_name = video_data['resolution']
        
        # Run detection
        has_subs, conf, text, meta = detector.detect_in_video(video_path, use_roi=True)
        
        # Update confusion matrix
        if has_subs and expected:
            tp += 1
            status = "✅ TP"
        elif not has_subs and not expected:
            tn += 1
            status = "✅ TN"
        elif has_subs and not expected:
            fp += 1
            status = "❌ FP"
        else:
            fn += 1
            status = "❌ FN"
        
        # Track by resolution
        if resolution_name not in results_by_resolution:
            results_by_resolution[resolution_name] = {'tp': 0, 'tn': 0, 'fp': 0, 'fn': 0}
        
        if tp + tn + fp + fn == idx:  # Just updated
            if status == "✅ TP":
                results_by_resolution[resolution_name]['tp'] += 1
            elif status == "✅ TN":
                results_by_resolution[resolution_name]['tn'] += 1
            elif status == "❌ FP":
                results_by_resolution[resolution_name]['fp'] += 1
            else:
                results_by_resolution[resolution_name]['fn'] += 1
        
        # Print non-TN results
        if status != "✅ TN":
            frames_info = f"{meta['frames_with_text']}/{meta['frames_analyzed']}"
            print(f"{idx:2d}. {status} {video_data['filename']:<25} conf={conf:.2f} frames={frames_info} res={meta['resolution']}")
    
    # Calculate overall metrics
    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    print("\n" + "=" * 70)
    print("📈 OVERALL RESULTS:")
    print("=" * 70)
    print(f"Confusion Matrix:")
    print(f"  TP: {tp:2}/8 WITH subtitles    ({tp/8*100:.0f}%)")
    print(f"  TN: {tn:2}/8 WITHOUT subtitles ({tn/8*100:.0f}%)")
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
    
    # Per-resolution breakdown
    print("\n" + "=" * 70)
    print("📊 RESULTS BY RESOLUTION:")
    print("=" * 70)
    
    for res_name in ['720p', '1080p', '1440p', '4K']:
        if res_name in results_by_resolution:
            r = results_by_resolution[res_name]
            res_tp, res_tn, res_fp, res_fn = r['tp'], r['tn'], r['fp'], r['fn']
            res_total = res_tp + res_tn + res_fp + res_fn
            res_accuracy = (res_tp + res_tn) / res_total if res_total > 0 else 0
            
            print(f"\n{res_name}:")
            print(f"  TP={res_tp}, TN={res_tn}, FP={res_fp}, FN={res_fn}")
            print(f"  Accuracy: {res_accuracy*100:.0f}%")
    
    print("\n" + "=" * 70)
    
    if recall >= 0.90 and f1 >= 0.90 and fpr <= 0.05:
        print("🎉 SPRINT 01 COMPLETE! Multi-resolution support VALIDATED!")
    else:
        print("⚠️  Sprint 01 gates not met - need improvements")
    
    print("=" * 70)
    
    return {
        'confusion_matrix': {'TP': tp, 'TN': tn, 'FP': fp, 'FN': fn},
        'metrics': {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'fpr': fpr,
            'f1_score': f1
        },
        'gates_passed': recall >= 0.90 and f1 >= 0.90 and fpr <= 0.05,
        'results_by_resolution': results_by_resolution
    }


if __name__ == '__main__':
    run_multi_resolution_baseline()
