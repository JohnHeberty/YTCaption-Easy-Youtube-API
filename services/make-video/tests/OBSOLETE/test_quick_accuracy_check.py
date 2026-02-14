"""
Quick Accuracy Check - Minimal test to verify ensemble works with 2 models
Tests Sprint 06 and Sprint 07 on 1-2 videos to quickly validate functionality
"""

import pytest
from pathlib import Path

from app.video_processing.ensemble_detector import EnsembleSubtitleDetector
from app.video_processing.detectors.clip_classifier import CLIPClassifier
from app.video_processing.detectors.easyocr_detector import EasyOCRDetector


class TestQuickAccuracyCheck:
    """Quick tests to verify basic accuracy measurement works"""
    
    @pytest.fixture(scope="class")
    def test_videos(self):
        """Get 2 test videos (1 with subtitles, 1 without)"""
        storage_path = Path(__file__).parent.parent / "storage" / "validation"
        
        videos = {
            'with_subs': storage_path / "sample_OK" / "5Bc-aOe4pC4.mp4",
            'without_subs': storage_path / "sample_NOT_OK" / "07EbeE3BRIw.mp4"
        }
        
        # Filter to existing videos
        return {k: v for k, v in videos.items() if v.exists()}
    
    def test_sprint06_quick_check(self, test_videos):
        """Quick test: Sprint 06 (2 models, weighted voting)"""
        if not test_videos:
            pytest.skip("No test videos available")
        
        print("\n" + "="*50)
        print("QUICK CHECK: SPRINT 06 BASELINE")
        print("="*50)
        
        # Sprint 06: Weighted voting
        ensemble = EnsembleSubtitleDetector(
            detectors=[
                CLIPClassifier(device='cpu'),
                EasyOCRDetector(gpu=False)
            ],
            voting_method='weighted'
        )
        
        results = {}
        for name, video_path in test_videos.items():
            print(f"\n🎥 Testing: {name}")
            print(f"   Path: {video_path.name}")
            
            result = ensemble.detect(str(video_path))
            
            print(f"   Result: {result['has_subtitles']}")
            print(f"   Confidence: {result['confidence']:.1f}%")
            print(f"   Votes: {result['votes']}")
            
            results[name] = result
        
        print("\n" + "="*50)
        print("✅ Sprint 06 quick check completed")
        print("="*50)
        
        assert len(results) > 0, "No results"
    
    def test_sprint07_quick_check(self, test_videos):
        """Quick test: Sprint 07 (2 models, confidence-weighted + analysis)"""
        if not test_videos:
            pytest.skip("No test videos available")
        
        print("\n" + "="*50)
        print("QUICK CHECK: SPRINT 07 ADVANCED")
        print("="*50)
        
        # Sprint 07: Confidence-weighted + conflict detection + uncertainty
        ensemble = EnsembleSubtitleDetector(
            detectors=[
                CLIPClassifier(device='cpu'),
                EasyOCRDetector(gpu=False)
            ],
            voting_method='confidence_weighted',
            enable_conflict_detection=True,
            enable_uncertainty_estimation=True
        )
        
        results = {}
        for name, video_path in test_videos.items():
            print(f"\n🎥 Testing: {name}")
            print(f"   Path: {video_path.name}")
            
            result = ensemble.detect(str(video_path))
            
            print(f"   Result: {result['has_subtitles']}")
            print(f"   Confidence: {result['confidence']:.1f}%")
            print(f"   Votes: {result['votes']}")
            
            if 'conflict_analysis' in result:
                conflict = result['conflict_analysis']
                print(f"   Conflict: {conflict.get('detected', False)}")
                if conflict.get('detected'):
                    print(f"   Severity: {conflict.get('severity', 'N/A')}")
            
            if 'uncertainty' in result:
                uncertainty = result['uncertainty']
                print(f"   Uncertainty: {uncertainty.get('aggregate', 0):.3f}")
                print(f"   Level: {uncertainty.get('level', 'N/A')}")
            
            results[name] = result
        
        print("\n" + "="*50)
        print("✅ Sprint 07 quick check completed")
        print("="*50)
        
        assert len(results) > 0, "No results"
    
    def test_compare_sprint06_vs_sprint07(self, test_videos):
        """Compare Sprint 06 vs Sprint 07 on same videos"""
        if not test_videos:
            pytest.skip("No test videos available")
        
        print("\n" + "="*50)
        print("COMPARISON: SPRINT 06 vs SPRINT 07")
        print("="*50)
        
        # Create both ensembles
        s06 = EnsembleSubtitleDetector(
            detectors=[
                CLIPClassifier(device='cpu'),
                EasyOCRDetector(gpu=False)
            ],
            voting_method='weighted'
        )
        
        s07 = EnsembleSubtitleDetector(
            detectors=[
                CLIPClassifier(device='cpu'),
                EasyOCRDetector(gpu=False)
            ],
            voting_method='confidence_weighted',
            enable_conflict_detection=True,
            enable_uncertainty_estimation=True
        )
        
        for name, video_path in test_videos.items():
            print(f"\n🎥 Video: {name} ({video_path.name})")
            
            # Sprint 06
            r06 = s06.detect(str(video_path))
            print(f"   S06: {r06['has_subtitles']} (conf: {r06['confidence']:.1f}%)")
            
            # Sprint 07
            r07 = s07.detect(str(video_path))
            print(f"   S07: {r07['has_subtitles']} (conf: {r07['confidence']:.1f}%)")
            
            # Compare
            if r06['has_subtitles'] == r07['has_subtitles']:
                print(f"   ✅ Both agree: {r06['has_subtitles']}")
            else:
                print(f"   ⚠️ DISAGREE: S06={r06['has_subtitles']} vs S07={r07['has_subtitles']}")
        
        print("\n" + "="*50)
        print("✅ Comparison completed")
        print("="*50)
