#!/usr/bin/env python3
"""
pose_validator.py — Standalone Pose Validator for SE11 Pipeline Integration

Called as subprocess by SE11 pipeline to validate pose between original
and inpainted images. Returns JSON with recommendation for retry logic.

Usage:
    # Basic validation
    python pose_validator.py --original input.png --inpainted output.png

    # JSON output (for pipeline)
    python pose_validator.py --original input.png --inpainted output.png --json

    # With attempt tracking
    python pose_validator.py --original input.png --inpainted output.png --attempt 2 --max-attempts 3

    # Strict mode (zero tolerance)
    python pose_validator.py --original input.png --inpainted output.png --strict

Output (JSON):
    {
        "pose_changed": true,
        "confidence": 0.95,
        "attempt": 1,
        "max_attempts": 3,
        "recommendation": "retry",
        "details": {
            "head_pct": 0.5,
            "torso_pct": 0.8,
            "limbs_pct": 2.1,
            "head_changed": true,
            "torso_changed": true,
            "limbs_changed": true
        }
    }

Exit codes:
    0 = POSE SAME (accept)
    1 = POSE CHANGED (retry or release)
    2 = Error (detection failed)

Dependencies:
    mediapipe==0.10.8
    opencv-python
    numpy
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Import from pose_detector (same directory)
sys.path.insert(0, str(Path(__file__).parent))
from pose_detector import detect_pose, detect_pose_multi, compare_poses, compare_angles


def validate_pose(
    original_path: str | Path,
    inpainted_path: str | Path,
    attempt: int = 1,
    max_attempts: int = 3,
    strict: bool = False,
    strict_threshold_pct: float = 0.1,
    head_threshold_pct: float = 0.3,
    torso_threshold_pct: float = 0.5,
    limbs_threshold_pct: float = 1.5,
    runs: int = 1,
) -> dict:
    """Validate pose between original and inpainted images.

    Args:
        original_path: Path to original image
        inpainted_path: Path to inpainted image
        attempt: Current attempt number (1-based)
        max_attempts: Maximum number of attempts allowed
        strict: Zero tolerance mode
        strict_threshold_pct: Per-landmark threshold in strict mode
        head_threshold_pct: Head change threshold
        torso_threshold_pct: Torso change threshold
        limbs_threshold_pct: Limbs change threshold
        runs: Number of detection runs to average

    Returns:
        dict with pose_changed, confidence, recommendation, details
    """
    try:
        # Detect poses
        if runs > 1:
            original = detect_pose_multi(original_path, runs=runs)
            inpainted = detect_pose_multi(inpainted_path, runs=runs)
        else:
            original = detect_pose(original_path)
            inpainted = detect_pose(inpainted_path)

        if original is None:
            return {
                "error": f"No pose detected in {original_path}",
                "pose_changed": False,
                "recommendation": "accept",
                "confidence": 0.0,
                "attempt": attempt,
                "max_attempts": max_attempts,
            }

        if inpainted is None:
            return {
                "error": f"No pose detected in {inpainted_path}",
                "pose_changed": False,
                "recommendation": "accept",
                "confidence": 0.0,
                "attempt": attempt,
                "max_attempts": max_attempts,
            }

        # Compare poses
        comparison = compare_poses(
            original, inpainted,
            head_threshold_pct=head_threshold_pct,
            torso_threshold_pct=torso_threshold_pct,
            limbs_threshold_pct=limbs_threshold_pct,
            strict=strict,
            strict_threshold_pct=strict_threshold_pct,
        )

        # Determine recommendation
        if not comparison.pose_changed:
            recommendation = "accept"
        elif attempt < max_attempts:
            recommendation = "retry"
        else:
            recommendation = "release_anyway"

        # Compute details
        head_diffs = [d for d in comparison.diffs if d.group == "HEAD"]
        torso_diffs = [d for d in comparison.diffs if d.group == "TORSO"]
        limb_diffs = [d for d in comparison.diffs if d.group == "LIMB"]

        import numpy as np
        head_pct = float(np.mean([d.distance_normalized for d in head_diffs])) if head_diffs else 0.0
        torso_pct = float(np.mean([d.distance_normalized for d in torso_diffs])) if torso_diffs else 0.0
        limbs_pct = float(np.mean([d.distance_normalized for d in limb_diffs])) if limb_diffs else 0.0

        max_landmark = round(float(max(d.distance_normalized for d in comparison.diffs)), 3) if comparison.diffs else 0.0

        return {
            "pose_changed": bool(comparison.pose_changed),
            "confidence": round(float(comparison.confidence), 3),
            "attempt": attempt,
            "max_attempts": max_attempts,
            "recommendation": recommendation,
            "strict_mode": strict,
            "details": {
                "head_pct": round(head_pct, 3),
                "torso_pct": round(torso_pct, 3),
                "limbs_pct": round(limbs_pct, 3),
                "head_changed": bool(comparison.head_changed),
                "torso_changed": bool(comparison.torso_changed),
                "limbs_changed": bool(comparison.limbs_changed),
                "max_landmark_pct": max_landmark,
                "overall_score": max_landmark,
            },
        }

    except Exception as e:
        return {
            "error": str(e),
            "pose_changed": False,
            "recommendation": "accept",
            "confidence": 0.0,
            "attempt": attempt,
            "max_attempts": max_attempts,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Pose Validator for SE11 Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --original input.png --inpainted output.png
  %(prog)s --original input.png --inpainted output.png --json
  %(prog)s --original input.png --inpainted output.png --attempt 2 --max-attempts 3
  %(prog)s --original input.png --inpainted output.png --strict

Exit codes:
  0 = POSE SAME (accept)
  1 = POSE CHANGED (retry or release)
  2 = Error (detection failed)
        """,
    )

    parser.add_argument("--original", "-o", required=True, help="Path to original image")
    parser.add_argument("--inpainted", "-i", required=True, help="Path to inpainted image")
    parser.add_argument("--attempt", type=int, default=1, help="Current attempt number (default: 1)")
    parser.add_argument("--max-attempts", type=int, default=3, help="Maximum attempts allowed (default: 3)")
    parser.add_argument("--strict", action="store_true", help="Zero tolerance mode")
    parser.add_argument("--strict-threshold", type=float, default=0.1,
                        help="Per-landmark threshold for strict mode (default: 0.1%%)")
    parser.add_argument("--head-threshold", type=float, default=0.3,
                        help="Head change threshold %% (default: 0.3)")
    parser.add_argument("--torso-threshold", type=float, default=0.5,
                        help="Torso change threshold %% (default: 0.5)")
    parser.add_argument("--limbs-threshold", type=float, default=1.5,
                        help="Limbs change threshold %% (default: 1.5)")
    parser.add_argument("--runs", type=int, default=1,
                        help="Number of detection runs to average (default: 1)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    result = validate_pose(
        original_path=args.original,
        inpainted_path=args.inpainted,
        attempt=args.attempt,
        max_attempts=args.max_attempts,
        strict=args.strict,
        strict_threshold_pct=args.strict_threshold,
        head_threshold_pct=args.head_threshold,
        torso_threshold_pct=args.torso_threshold,
        limbs_threshold_pct=args.limbs_threshold,
        runs=args.runs,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        # Human-readable output
        if result.get("error"):
            print(f"ERROR: {result['error']}")
            sys.exit(2)

        status = "POSE CHANGED" if result["pose_changed"] else "POSE SAME"
        print(f"Status: {status}")
        print(f"Confidence: {result['confidence']:.1%}")
        print(f"Attempt: {result['attempt']}/{result['max_attempts']}")
        print(f"Recommendation: {result['recommendation'].upper()}")

        details = result.get("details", {})
        print(f"\nDetails:")
        print(f"  Head:   {details.get('head_pct', 0):.3f}% {'CHANGED' if details.get('head_changed') else 'stable'}")
        print(f"  Torso:  {details.get('torso_pct', 0):.3f}% {'CHANGED' if details.get('torso_changed') else 'stable'}")
        print(f"  Limbs:  {details.get('limbs_pct', 0):.3f}% {'CHANGED' if details.get('limbs_changed') else 'stable'}")
        print(f"  Max landmark: {details.get('max_landmark_pct', 0):.3f}%")

    # Exit code: 0=same, 1=changed, 2=error
    if result.get("error"):
        sys.exit(2)
    elif result["pose_changed"]:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
