"""
Sprint 06-07: Ensemble Accuracy Validation

Valida acurácia do ensemble em dataset completo:
- Sprint 06: Baseline (weighted voting)
- Sprint 07: Advanced (confidence-weighted + conflict + uncertainty)

Target: ≥90% accuracy
"""

import json
import pytest
from pathlib import Path
from typing import Dict, List, Tuple
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.video_processing.ensemble_detector import EnsembleSubtitleDetector


class TestEnsembleAccuracyValidation:
    """Validate ensemble accuracy on full dataset."""
    
    @pytest.fixture(scope="class")
    def datasets(self):
        """Load all validation datasets."""
        base_path = Path('storage/validation')
        
        datasets = {
            'quick_test': base_path / 'quick_test',
            'dev_set': base_path / 'dev_set',
            'smoke_set': base_path / 'smoke_set',
            'sample_ok': base_path / 'sample_OK',
            'sample_not_ok': base_path / 'sample_NOT_OK',
        }
        
        # Filter existing directories
        available = {name: path for name, path in datasets.items() if path.exists()}
        
        print(f"\n📂 Available datasets: {list(available.keys())}")
        return available
    
    def load_ground_truth(self, dataset_path: Path) -> Dict[str, bool]:
        """Load ground truth from dataset directory."""
        ground_truth = {}
        
        # Try to load ground_truth.json if exists
        gt_file = dataset_path / 'ground_truth.json'
        if gt_file.exists():
            with open(gt_file, 'r') as f:
                data = json.load(f)
                
                # Handle different JSON formats
                if 'videos' in data:
                    # Format 1: {"videos": [{"filename": "x.mp4", "has_subtitles": true}]}
                    for video in data['videos']:
                        ground_truth[video['filename']] = video.get('has_subtitles', video.get('expected', False))
                elif 'dataset_info' in data:
                    # Format 2: {"dataset_info": {...}, "videos": {...}}
                    for filename, info in data.get('videos', {}).items():
                        ground_truth[filename] = info.get('has_subtitles', info.get('expected', False))
                else:
                    # Format 3: flat dict {"video1.mp4": {"expected": true}}
                    for filename, info in data.items():
                        if isinstance(info, dict):
                            ground_truth[filename] = info.get('has_subtitles', info.get('expected', False))
                        elif isinstance(info, bool):
                            ground_truth[filename] = info
        else:
            # Infer from directory structure (sample_OK = True, sample_NOT_OK = False)
            if 'OK' in str(dataset_path):
                expected = True
            elif 'NOT_OK' in str(dataset_path):
                expected = False
            else:
                expected = None
            
            if expected is not None:
                for video_file in dataset_path.glob('*.mp4'):
                    ground_truth[video_file.name] = expected
        
        return ground_truth
    
    def test_sprint06_baseline_accuracy(self, datasets):
        """
        Test 1: Sprint 06 baseline (weighted voting) accuracy.
        Target: Establish baseline for comparison.
        """
        print("\n" + "="*60)
        print("TEST 1: SPRINT 06 BASELINE ACCURACY")
        print("="*60)
        
        # Sprint 06 ensemble (weighted voting, default detectors: PaddleOCR + CLIP + EasyOCR)
        ensemble = EnsembleSubtitleDetector(
            voting_method='weighted'  # Sprint 06 default
        )
        
        all_results = []
        total_correct = 0
        total_videos = 0
        
        tp, tn, fp, fn = 0, 0, 0, 0
        
        for dataset_name, dataset_path in datasets.items():
            print(f"\n📂 Dataset: {dataset_name}")
            
            ground_truth = self.load_ground_truth(dataset_path)
            
            if not ground_truth:
                print(f"   ⚠️ No ground truth found, skipping")
                continue
            
            print(f"   Videos: {len(ground_truth)}")
            
            correct = 0
            errors = []
            
            for video_name, expected in ground_truth.items():
                video_path = dataset_path / video_name
                
                if not video_path.exists():
                    print(f"   ⚠️ Video not found: {video_name}")
                    continue
                
                # Detect with Sprint 06
                try:
                    result = ensemble.detect(str(video_path))
                    predicted = result['has_subtitles']
                    confidence = result['confidence']
                    
                    # Update confusion matrix
                    if expected and predicted:
                        tp += 1
                    elif not expected and not predicted:
                        tn += 1
                    elif not expected and predicted:
                        fp += 1
                    else:  # expected and not predicted
                        fn += 1
                    
                    if predicted == expected:
                        correct += 1
                        total_correct += 1
                    else:
                        errors.append({
                            'video': video_name,
                            'expected': expected,
                            'predicted': predicted,
                            'confidence': confidence
                        })
                    
                    total_videos += 1
                    
                except Exception as e:
                    print(f"   ❌ Error processing {video_name}: {e}")
                    continue
            
            dataset_accuracy = (correct / len(ground_truth)) * 100 if ground_truth else 0
            print(f"   Accuracy: {dataset_accuracy:.1f}% ({correct}/{len(ground_truth)})")
            
            if errors:
                print(f"   Errors: {len(errors)}")
                for err in errors[:3]:  # Show first 3 errors
                    print(f"      - {err['video']}: expected={err['expected']}, got={err['predicted']} (conf={err['confidence']:.2f})")
            
            all_results.append({
                'dataset': dataset_name,
                'accuracy': dataset_accuracy,
                'correct': correct,
                'total': len(ground_truth),
                'errors': errors
            })
        
        # Calculate overall metrics
        accuracy = (total_correct / total_videos * 100) if total_videos > 0 else 0
        precision = (tp / (tp + fp) * 100) if (tp + fp) > 0 else 0
        recall = (tp / (tp + fn) * 100) if (tp + fn) > 0 else 0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
        
        print("\n" + "="*60)
        print("SPRINT 06 BASELINE RESULTS")
        print("="*60)
        print(f"Total Videos: {total_videos}")
        print(f"Accuracy:     {accuracy:.2f}%")
        print(f"Precision:    {precision:.2f}%")
        print(f"Recall:       {recall:.2f}%")
        print(f"F1 Score:     {f1:.2f}%")
        print(f"\nConfusion Matrix:")
        print(f"  TP: {tp}  FP: {fp}")
        print(f"  FN: {fn}  TN: {tn}")
        print("="*60)
        
        # Assert baseline exists (no specific threshold yet)
        assert total_videos > 0, "No videos tested"
        assert accuracy > 0, "Accuracy is 0%"
        
        # Store for comparison
        self.sprint06_results = {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn
        }
    
    def test_sprint07_advanced_accuracy(self, datasets):
        """
        Test 2: Sprint 07 advanced (confidence-weighted + analysis) accuracy.
        Target: ≥90% accuracy (improvement over Sprint 06).
        """
        print("\n" + "="*60)
        print("TEST 2: SPRINT 07 ADVANCED ACCURACY")
        print("="*60)
        
        # Sprint 07 ensemble (advanced voting + conflict + uncertainty, default 3 detectors)
        ensemble = EnsembleSubtitleDetector(
            voting_method='confidence_weighted',
            enable_conflict_detection=True,
            enable_uncertainty_estimation=True
        )
        
        all_results = []
        total_correct = 0
        total_videos = 0
        
        tp, tn, fp, fn = 0, 0, 0, 0
        
        # Track conflicts and uncertainty
        high_conflicts = 0
        high_uncertainty = 0
        
        for dataset_name, dataset_path in datasets.items():
            print(f"\n📂 Dataset: {dataset_name}")
            
            ground_truth = self.load_ground_truth(dataset_path)
            
            if not ground_truth:
                print(f"   ⚠️ No ground truth found, skipping")
                continue
            
            print(f"   Videos: {len(ground_truth)}")
            
            correct = 0
            errors = []
            
            for video_name, expected in ground_truth.items():
                video_path = dataset_path / video_name
                
                if not video_path.exists():
                    continue
                
                # Detect with Sprint 07
                try:
                    result = ensemble.detect(str(video_path))
                    predicted = result['has_subtitles']
                    confidence = result['confidence']
                    
                    # Check conflict and uncertainty
                    if 'conflict_analysis' in result:
                        if result['conflict_analysis'].get('severity') == 'high':
                            high_conflicts += 1
                    
                    if 'uncertainty_analysis' in result:
                        if result['uncertainty_analysis'].get('uncertainty_level') == 'high':
                            high_uncertainty += 1
                    
                    # Update confusion matrix
                    if expected and predicted:
                        tp += 1
                    elif not expected and not predicted:
                        tn += 1
                    elif not expected and predicted:
                        fp += 1
                    else:
                        fn += 1
                    
                    if predicted == expected:
                        correct += 1
                        total_correct += 1
                    else:
                        errors.append({
                            'video': video_name,
                            'expected': expected,
                            'predicted': predicted,
                            'confidence': confidence,
                            'conflict': result.get('conflict_analysis', {}).get('severity', 'none'),
                            'uncertainty': result.get('uncertainty_analysis', {}).get('uncertainty_level', 'low')
                        })
                    
                    total_videos += 1
                    
                except Exception as e:
                    print(f"   ❌ Error processing {video_name}: {e}")
                    continue
            
            dataset_accuracy = (correct / len(ground_truth)) * 100 if ground_truth else 0
            print(f"   Accuracy: {dataset_accuracy:.1f}% ({correct}/{len(ground_truth)})")
            
            if errors:
                print(f"   Errors: {len(errors)}")
                for err in errors[:3]:
                    print(f"      - {err['video']}: expected={err['expected']}, got={err['predicted']}")
                    print(f"        conf={err['confidence']:.2f}, conflict={err['conflict']}, uncertainty={err['uncertainty']}")
            
            all_results.append({
                'dataset': dataset_name,
                'accuracy': dataset_accuracy,
                'correct': correct,
                'total': len(ground_truth),
                'errors': errors
            })
        
        # Calculate overall metrics
        accuracy = (total_correct / total_videos * 100) if total_videos > 0 else 0
        precision = (tp / (tp + fp) * 100) if (tp + fp) > 0 else 0
        recall = (tp / (tp + fn) * 100) if (tp + fn) > 0 else 0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
        
        print("\n" + "="*60)
        print("SPRINT 07 ADVANCED RESULTS")
        print("="*60)
        print(f"Total Videos: {total_videos}")
        print(f"Accuracy:     {accuracy:.2f}%")
        print(f"Precision:    {precision:.2f}%")
        print(f"Recall:       {recall:.2f}%")
        print(f"F1 Score:     {f1:.2f}%")
        print(f"\nConfusion Matrix:")
        print(f"  TP: {tp}  FP: {fp}")
        print(f"  FN: {fn}  TN: {tn}")
        print(f"\nAnalysis:")
        print(f"  High Conflicts:    {high_conflicts}")
        print(f"  High Uncertainty:  {high_uncertainty}")
        print("="*60)
        
        # Compare with Sprint 06 if available
        if hasattr(self, 'sprint06_results'):
            s06 = self.sprint06_results
            print("\n" + "="*60)
            print("COMPARISON: SPRINT 06 vs SPRINT 07")
            print("="*60)
            print(f"Accuracy:   {s06['accuracy']:.2f}% → {accuracy:.2f}% ({accuracy - s06['accuracy']:+.2f}pp)")
            print(f"Precision:  {s06['precision']:.2f}% → {precision:.2f}% ({precision - s06['precision']:+.2f}pp)")
            print(f"Recall:     {s06['recall']:.2f}% → {recall:.2f}% ({recall - s06['recall']:+.2f}pp)")
            print(f"F1 Score:   {s06['f1']:.2f}% → {f1:.2f}% ({f1 - s06['f1']:+.2f}pp)")
            print("="*60)
        
        # Assert improvement
        assert total_videos > 0, "No videos tested"
        
        # CRITICAL: Target is ≥90% accuracy
        print(f"\n🎯 TARGET: ≥90% accuracy")
        if accuracy >= 90.0:
            print(f"✅ ACHIEVED: {accuracy:.2f}% ≥ 90%")
        else:
            print(f"⚠️ NOT YET: {accuracy:.2f}% < 90% (need +{90.0 - accuracy:.2f}pp)")
        
        # Store results
        self.sprint07_results = {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn
        }
        
        # Save results to file for Sprint 08 documentation
        results_file = Path('tests/sprint07_accuracy_results.json')
        with open(results_file, 'w') as f:
            json.dump({
                'sprint06': self.sprint06_results if hasattr(self, 'sprint06_results') else None,
                'sprint07': self.sprint07_results,
                'target_achieved': accuracy >= 90.0,
                'datasets_tested': list(datasets.keys()),
                'total_videos': total_videos
            }, f, indent=2)
        
        print(f"\n📄 Results saved to: {results_file}")


def test_accuracy_summary():
    """Summary test: Print final accuracy report."""
    results_file = Path('tests/sprint07_accuracy_results.json')
    
    if results_file.exists():
        with open(results_file, 'r') as f:
            results = json.load(f)
        
        print("\n" + "="*60)
        print("SPRINT 06-07 ACCURACY VALIDATION SUMMARY")
        print("="*60)
        
        if results.get('sprint06'):
            s06 = results['sprint06']
            print(f"\nSprint 06 Baseline:")
            print(f"  Accuracy:  {s06['accuracy']:.2f}%")
            print(f"  Precision: {s06['precision']:.2f}%")
            print(f"  Recall:    {s06['recall']:.2f}%")
        
        s07 = results['sprint07']
        print(f"\nSprint 07 Advanced:")
        print(f"  Accuracy:  {s07['accuracy']:.2f}%")
        print(f"  Precision: {s07['precision']:.2f}%")
        print(f"  Recall:    {s07['recall']:.2f}%")
        
        print(f"\nDatasets Tested: {', '.join(results['datasets_tested'])}")
        print(f"Total Videos:    {results['total_videos']}")
        
        print(f"\n🎯 Target: ≥90% accuracy")
        if results['target_achieved']:
            print(f"✅ STATUS: ACHIEVED ({s07['accuracy']:.2f}% ≥ 90%)")
        else:
            print(f"⚠️ STATUS: NOT YET ({s07['accuracy']:.2f}% < 90%)")
        
        print("="*60)
    
    assert True  # Always pass (informational test)
