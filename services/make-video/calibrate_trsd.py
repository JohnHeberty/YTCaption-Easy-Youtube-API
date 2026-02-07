#!/usr/bin/env python3
"""
TRSD Calibration Script - Sprint 08
Processes labeled dataset (OK/NOT_OK) to optimize thresholds
"""
import sys
import os
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import logging

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.video_validator import VideoValidator
from app.config import Settings
from app.subtitle_classifier import ClassificationResult, TrackCategory


@dataclass
class VideoTestCase:
    """Represents one labeled video"""
    video_path: Path
    expected_result: bool  # True = should approve (OK), False = should block (NOT_OK)
    video_id: str
    
    
@dataclass
class DetectionResult:
    """Result from TRSD detection"""
    video_id: str
    expected: bool
    detected_subtitles: bool
    decision: str  # "TP", "TN", "FP", "FN"
    processing_time: float
    classification: Optional[ClassificationResult]
    error: Optional[str] = None


@dataclass
class CalibrationMetrics:
    """Overall calibration metrics"""
    total: int
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    avg_processing_time: float


class TRSDCalibrator:
    """Calibrates TRSD thresholds using labeled dataset"""
    
    def __init__(self, ok_dir: Path, not_ok_dir: Path, output_dir: Path):
        self.ok_dir = ok_dir
        self.not_ok_dir = not_ok_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Enable TRSD and debug mode
        os.environ['TRSD_ENABLED'] = 'true'
        os.environ['TRSD_SAVE_DEBUG_ARTIFACTS'] = 'true'
        os.environ['TRSD_SAVE_DETECTION_EVENTS'] = 'true'
        
        self.settings = Settings()
        
    def load_dataset(self) -> List[VideoTestCase]:
        """Load all labeled videos"""
        test_cases = []
        
        # Load OK videos (should approve)
        for video_file in self.ok_dir.glob("*.mp4"):
            test_cases.append(VideoTestCase(
                video_path=video_file,
                expected_result=True,  # Should approve (no subtitles or only static)
                video_id=video_file.stem
            ))
        
        # Load NOT_OK videos (should block)
        for video_file in self.not_ok_dir.glob("*.mp4"):
            test_cases.append(VideoTestCase(
                video_path=video_file,
                expected_result=False,  # Should block (has subtitles)
                video_id=video_file.stem
            ))
        
        self.logger.info(f"Loaded {len(test_cases)} test cases:")
        self.logger.info(f"  - OK (approve): {len(list(self.ok_dir.glob('*.mp4')))}")
        self.logger.info(f"  - NOT_OK (block): {len(list(self.not_ok_dir.glob('*.mp4')))}")
        
        return test_cases
    
    def process_video(self, test_case: VideoTestCase) -> DetectionResult:
        """Process one video with TRSD"""
        self.logger.info(f"Processing: {test_case.video_id} (expect {'APPROVE' if test_case.expected_result else 'BLOCK'})")
        
        start_time = time.time()
        
        try:
            # Instantiate VideoValidator with correct parameters
            validator = VideoValidator(min_confidence=0.50, frames_per_second=6, max_frames=240)
            has_subtitles, confidence, method = validator.has_embedded_subtitles(str(test_case.video_path))
            
            # Get classification from TRSD telemetry if available
            classification = None  # Will be populated from telemetry in future
            
            processing_time = time.time() - start_time
            
            # Determine decision type
            # expected=True means should approve (no subtitles blocking)
            # has_subtitles=True means detected subtitles (should block)
            if test_case.expected_result:  # Should approve
                if not has_subtitles:
                    decision = "TN"  # True Negative - correctly approved
                else:
                    decision = "FP"  # False Positive - incorrectly blocked
            else:  # Should block (NOT_OK)
                if has_subtitles:
                    decision = "TP"  # True Positive - correctly blocked
                else:
                    decision = "FN"  # False Negative - incorrectly approved
            
            result = DetectionResult(
                video_id=test_case.video_id,
                expected=test_case.expected_result,
                detected_subtitles=has_subtitles,
                decision=decision,
                processing_time=processing_time,
                classification=classification
            )
            
            self.logger.info(f"  Result: {decision} - has_subtitles={has_subtitles}, time={processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            self.logger.error(f"  ERROR: {str(e)}")
            return DetectionResult(
                video_id=test_case.video_id,
                expected=test_case.expected_result,
                detected_subtitles=False,
                decision="ERROR",
                processing_time=time.time() - start_time,
                classification=None,
                error=str(e)
            )
    
    def calculate_metrics(self, results: List[DetectionResult]) -> CalibrationMetrics:
        """Calculate precision, recall, F1"""
        # Filter out errors
        valid_results = [r for r in results if r.decision != "ERROR"]
        
        tp = sum(1 for r in valid_results if r.decision == "TP")
        tn = sum(1 for r in valid_results if r.decision == "TN")
        fp = sum(1 for r in valid_results if r.decision == "FP")
        fn = sum(1 for r in valid_results if r.decision == "FN")
        
        total = len(valid_results)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / total if total > 0 else 0.0
        
        avg_time = sum(r.processing_time for r in valid_results) / total if total > 0 else 0.0
        
        return CalibrationMetrics(
            total=total,
            true_positives=tp,
            true_negatives=tn,
            false_positives=fp,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            accuracy=accuracy,
            avg_processing_time=avg_time
        )
    
    def save_results(self, results: List[DetectionResult], metrics: CalibrationMetrics):
        """Save calibration results to JSON"""
        output_file = self.output_dir / "calibration_results.json"
        
        data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "metrics": asdict(metrics),
            "results": [
                {
                    "video_id": r.video_id,
                    "expected": r.expected,
                    "detected_subtitles": r.detected_subtitles,
                    "decision": r.decision,
                    "processing_time": round(r.processing_time, 2),
                    "classification": {
                        "has_subtitles": r.classification.has_subtitles,
                        "confidence": r.classification.confidence,
                        "subtitle_count": r.classification.subtitle_count,
                        "static_count": r.classification.static_count,
                        "ambiguous_count": r.classification.ambiguous_count
                    } if r.classification else None,
                    "error": r.error
                }
                for r in results
            ],
            "config": {
                "trsd_enabled": self.settings.trsd_enabled,
                "ignore_static_text": self.settings.trsd_ignore_static_text,
                "static_min_presence": self.settings.trsd_static_min_presence,
                "static_max_change": self.settings.trsd_static_max_change,
                "subtitle_min_change_rate": self.settings.trsd_subtitle_min_change_rate,
                "screencast_min_detections": self.settings.trsd_screencast_min_detections,
                "track_iou_threshold": self.settings.trsd_track_iou_threshold
            }
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        self.logger.info(f"Results saved to: {output_file}")
    
    def generate_report(self, results: List[DetectionResult], metrics: CalibrationMetrics):
        """Generate human-readable report"""
        report_file = self.output_dir / "calibration_report.md"
        
        with open(report_file, 'w') as f:
            f.write("# TRSD Calibration Report\n\n")
            f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Overall Metrics
            f.write("## 📊 Overall Metrics\n\n")
            f.write(f"- **Total Videos:** {metrics.total}\n")
            f.write(f"- **Accuracy:** {metrics.accuracy:.2%}\n")
            f.write(f"- **Precision:** {metrics.precision:.2%} (when blocking, correct rate)\n")
            f.write(f"- **Recall:** {metrics.recall:.2%} (catch rate for videos with subtitles)\n")
            f.write(f"- **F1-Score:** {metrics.f1_score:.2%}\n")
            f.write(f"- **Avg Processing Time:** {metrics.avg_processing_time:.2f}s\n\n")
            
            # Confusion Matrix
            f.write("## 🎯 Confusion Matrix\n\n")
            f.write("```\n")
            f.write("                    Predicted\n")
            f.write("                APPROVE    BLOCK\n")
            f.write(f"Actual APPROVE     {metrics.true_negatives:2d}        {metrics.false_positives:2d}     (OK folder)\n")
            f.write(f"       BLOCK       {metrics.false_negatives:2d}        {metrics.true_positives:2d}     (NOT_OK folder)\n")
            f.write("```\n\n")
            
            # Detailed Results
            f.write("## 📋 Detailed Results\n\n")
            
            # False Positives (incorrectly blocked OK videos)
            fps = [r for r in results if r.decision == "FP"]
            if fps:
                f.write("### ❌ False Positives (incorrectly blocked)\n\n")
                for r in fps:
                    f.write(f"- **{r.video_id}** (from OK folder)\n")
                    if r.classification:
                        f.write(f"  - Subtitle tracks: {r.classification.subtitle_count}\n")
                        f.write(f"  - Static tracks: {r.classification.static_count}\n")
                        f.write(f"  - Ambiguous tracks: {r.classification.ambiguous_count}\n")
                    f.write("\n")
            
            # False Negatives (incorrectly approved NOT_OK videos)
            fns = [r for r in results if r.decision == "FN"]
            if fns:
                f.write("### ❌ False Negatives (incorrectly approved)\n\n")
                for r in fns:
                    f.write(f"- **{r.video_id}** (from NOT_OK folder)\n")
                    if r.classification:
                        f.write(f"  - Subtitle tracks: {r.classification.subtitle_count}\n")
                        f.write(f"  - Static tracks: {r.classification.static_count}\n")
                        f.write(f"  - Ambiguous tracks: {r.classification.ambiguous_count}\n")
                    f.write("\n")
            
            # Current Configuration
            f.write("## ⚙️ Current Configuration\n\n")
            f.write("```env\n")
            f.write(f"TRSD_ENABLED={self.settings.trsd_enabled}\n")
            f.write(f"TRSD_IGNORE_STATIC_TEXT={self.settings.trsd_ignore_static_text}\n")
            f.write(f"TRSD_STATIC_MIN_PRESENCE={self.settings.trsd_static_min_presence}\n")
            f.write(f"TRSD_STATIC_MAX_CHANGE={self.settings.trsd_static_max_change}\n")
            f.write(f"TRSD_SUBTITLE_MIN_CHANGE_RATE={self.settings.trsd_subtitle_min_change_rate}\n")
            f.write(f"TRSD_SCREENCAST_MIN_DETECTIONS={self.settings.trsd_screencast_min_detections}\n")
            f.write(f"TRSD_TRACK_IOU_THRESHOLD={self.settings.trsd_track_iou_threshold}\n")
            f.write("```\n\n")
            
            # Recommendations
            f.write("## 💡 Recommendations\n\n")
            
            if metrics.recall < 0.90:
                f.write("### ⚠️ Low Recall (missing subtitles)\n")
                f.write("Consider:\n")
                f.write("- Decrease `TRSD_SUBTITLE_MIN_CHANGE_RATE` to catch slower-changing subtitles\n")
                f.write("- Increase `TRSD_STATIC_MIN_PRESENCE` to be less aggressive on static classification\n")
                f.write("\n")
            
            if metrics.precision < 0.85:
                f.write("### ⚠️ Low Precision (false blocks)\n")
                f.write("Consider:\n")
                f.write("- Increase `TRSD_SUBTITLE_MIN_CHANGE_RATE` to be more confident\n")
                f.write("- Decrease `TRSD_STATIC_MIN_PRESENCE` to classify more as static\n")
                f.write("- Review false positives in debug artifacts\n")
                f.write("\n")
            
            if metrics.recall >= 0.90 and metrics.precision >= 0.85:
                f.write("### ✅ Good Performance!\n")
                f.write("Current configuration is working well. Consider:\n")
                f.write("- Testing with more diverse videos\n")
                f.write("- Enabling in production with A/B test\n")
                f.write("\n")
            
            # Next Steps
            f.write("## 🚀 Next Steps\n\n")
            f.write("1. Review debug artifacts in `storage/debug_artifacts/`\n")
            f.write("2. Analyze false positives/negatives\n")
            f.write("3. Adjust thresholds based on recommendations\n")
            f.write("4. Re-run calibration: `python calibrate_trsd.py`\n")
            f.write("5. Deploy to staging when metrics are acceptable\n")
        
        self.logger.info(f"Report saved to: {report_file}")
    
    def run(self):
        """Run full calibration"""
        self.logger.info("=" * 60)
        self.logger.info("TRSD Calibration - Sprint 08")
        self.logger.info("=" * 60)
        
        # Load dataset
        test_cases = self.load_dataset()
        
        if not test_cases:
            self.logger.error("No videos found in OK/NOT_OK folders!")
            return
        
        # Process all videos
        results = []
        for i, test_case in enumerate(test_cases, 1):
            self.logger.info(f"\n[{i}/{len(test_cases)}] Processing {test_case.video_id}")
            result = self.process_video(test_case)
            results.append(result)
        
        # Calculate metrics
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Calculating metrics...")
        metrics = self.calculate_metrics(results)
        
        # Print summary
        self.logger.info("\n" + "=" * 60)
        self.logger.info("CALIBRATION RESULTS")
        self.logger.info("=" * 60)
        self.logger.info(f"Total Videos: {metrics.total}")
        self.logger.info(f"Accuracy: {metrics.accuracy:.2%}")
        self.logger.info(f"Precision: {metrics.precision:.2%}")
        self.logger.info(f"Recall: {metrics.recall:.2%}")
        self.logger.info(f"F1-Score: {metrics.f1_score:.2%}")
        self.logger.info(f"Avg Time: {metrics.avg_processing_time:.2f}s")
        self.logger.info("-" * 60)
        self.logger.info(f"True Positives (correct blocks): {metrics.true_positives}")
        self.logger.info(f"True Negatives (correct approves): {metrics.true_negatives}")
        self.logger.info(f"False Positives (wrong blocks): {metrics.false_positives}")
        self.logger.info(f"False Negatives (wrong approves): {metrics.false_negatives}")
        self.logger.info("=" * 60)
        
        # Save results
        self.save_results(results, metrics)
        self.generate_report(results, metrics)
        
        self.logger.info("\n✅ Calibration complete!")
        self.logger.info(f"📊 See report: {self.output_dir / 'calibration_report.md'}")
        self.logger.info(f"📄 See JSON: {self.output_dir / 'calibration_results.json'}")


def main():
    """Main entry point"""
    # Paths
    base_dir = Path(__file__).parent
    ok_dir = base_dir / "storage" / "OK"
    not_ok_dir = base_dir / "storage" / "NOT_OK"
    output_dir = base_dir / "storage" / "calibration"
    
    # Validate directories
    if not ok_dir.exists():
        print(f"ERROR: OK directory not found: {ok_dir}")
        sys.exit(1)
    
    if not not_ok_dir.exists():
        print(f"ERROR: NOT_OK directory not found: {not_ok_dir}")
        sys.exit(1)
    
    # Run calibration
    calibrator = TRSDCalibrator(ok_dir, not_ok_dir, output_dir)
    calibrator.run()


if __name__ == "__main__":
    main()
