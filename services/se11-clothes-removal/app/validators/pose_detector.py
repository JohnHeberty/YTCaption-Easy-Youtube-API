#!/usr/bin/env python3
"""
pose_detector.py — Pose Detection & Comparison for SE11 NSFW Pipeline

Detects body poses in images using MediaPipe Pose and compares them
to determine if the pose changed between original and inpainted output.

Usage:
    # Compare two images
    python pose_detector.py --original pose1.png --inpainted pose2.png

    # Compare with verbose output
    python pose_detector.py --original pose1.png --inpainted pose2.png --verbose

    # Compare and generate visualization
    python pose_detector.py --original pose1.png --inpainted pose2.png --visualize

    # Only detect pose (no comparison)
    python pose_detector.py --detect pose1.png

Dependencies:
    mediapipe==0.10.8
    opencv-python
    numpy
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np

# Suppress MediaPipe GPU warnings (runs on CPU fine)
import logging
logging.getLogger("mediapipe").setLevel(logging.ERROR)

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

# ─── Landmark Groups ────────────────────────────────────────────────────────

HEAD_LANDMARKS = [
    mp_pose.PoseLandmark.NOSE,
    mp_pose.PoseLandmark.LEFT_EAR,
    mp_pose.PoseLandmark.RIGHT_EAR,
    mp_pose.PoseLandmark.LEFT_EYE,
    mp_pose.PoseLandmark.RIGHT_EYE,
    mp_pose.PoseLandmark.MOUTH_LEFT,
    mp_pose.PoseLandmark.MOUTH_RIGHT,
]

TORSO_LANDMARKS = [
    mp_pose.PoseLandmark.LEFT_SHOULDER,
    mp_pose.PoseLandmark.RIGHT_SHOULDER,
    mp_pose.PoseLandmark.LEFT_HIP,
    mp_pose.PoseLandmark.RIGHT_HIP,
]

LIMB_LANDMARKS = [
    mp_pose.PoseLandmark.LEFT_ELBOW,
    mp_pose.PoseLandmark.RIGHT_ELBOW,
    mp_pose.PoseLandmark.LEFT_WRIST,
    mp_pose.PoseLandmark.RIGHT_WRIST,
    mp_pose.PoseLandmark.LEFT_KNEE,
    mp_pose.PoseLandmark.RIGHT_KNEE,
    mp_pose.PoseLandmark.LEFT_ANKLE,
    mp_pose.PoseLandmark.RIGHT_ANKLE,
]

ALL_KEY_LANDMARKS = HEAD_LANDMARKS + TORSO_LANDMARKS + LIMB_LANDMARKS

# Landmark names for display
LANDMARK_NAMES = {
    0: "NOSE", 1: "LEFT_EYE_INNER", 2: "LEFT_EYE", 3: "LEFT_EYE_OUTER",
    4: "RIGHT_EYE_INNER", 5: "RIGHT_EYE", 6: "RIGHT_EYE_OUTER",
    7: "LEFT_EAR", 8: "RIGHT_EAR", 9: "MOUTH_LEFT", 10: "MOUTH_RIGHT",
    11: "LEFT_SHOULDER", 12: "RIGHT_SHOULDER", 13: "LEFT_ELBOW", 14: "RIGHT_ELBOW",
    15: "LEFT_WRIST", 16: "RIGHT_WRIST", 17: "LEFT_PINKY", 18: "RIGHT_PINKY",
    19: "LEFT_INDEX", 20: "RIGHT_INDEX", 21: "LEFT_THUMB", 22: "RIGHT_THUMB",
    23: "LEFT_HIP", 24: "RIGHT_HIP", 25: "LEFT_KNEE", 26: "RIGHT_KNEE",
    27: "LEFT_ANKLE", 28: "RIGHT_ANKLE", 29: "LEFT_HEEL", 30: "RIGHT_HEEL",
    31: "LEFT_FOOT_INDEX", 32: "RIGHT_FOOT_INDEX",
}


# ─── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class Landmark:
    """Single body landmark with position and confidence."""
    index: int
    name: str
    x: float  # pixel coordinates
    y: float
    z: float  # relative depth
    visibility: float  # 0-1 confidence


@dataclass
class PoseResult:
    """Complete pose detection result for one image."""
    landmarks: list[Landmark]
    image_width: int
    image_height: int
    detection_confidence: float

    @property
    def diagonal(self) -> float:
        return math.sqrt(self.image_width ** 2 + self.image_height ** 2)

    def get_landmark(self, landmark: mp_pose.PoseLandmark) -> Landmark:
        return self.landmarks[landmark.value]

    def to_dict(self) -> dict:
        return {
            "image_size": [self.image_width, self.image_height],
            "diagonal": round(self.diagonal, 1),
            "detection_confidence": round(self.detection_confidence, 3),
            "landmarks": {
                lm.name: {
                    "x": round(lm.x, 1),
                    "y": round(lm.y, 1),
                    "visibility": round(lm.visibility, 3),
                }
                for lm in self.landmarks
                if lm.visibility > 0.5
            },
        }


@dataclass
class LandmarkDiff:
    """Difference for a single landmark between two poses."""
    landmark: mp_pose.PoseLandmark
    name: str
    dx: float
    dy: float
    distance: float
    distance_normalized: float  # as % of image diagonal
    group: str  # HEAD, TORSO, LIMB


@dataclass
class PoseComparison:
    """Complete comparison result between two poses."""
    original: PoseResult
    inpainted: PoseResult
    diffs: list[LandmarkDiff]
    head_changed: bool
    torso_changed: bool
    limbs_changed: bool
    pose_changed: bool
    confidence: float
    summary: str

    def to_dict(self) -> dict:
        return {
            "pose_changed": bool(self.pose_changed),
            "confidence": round(float(self.confidence), 3),
            "head_changed": bool(self.head_changed),
            "torso_changed": bool(self.torso_changed),
            "limbs_changed": bool(self.limbs_changed),
            "summary": self.summary,
            "diffs": {
                d.name: {
                    "distance_px": round(float(d.distance), 1),
                    "distance_pct": round(float(d.distance_normalized), 2),
                    "group": d.group,
                }
                for d in self.diffs
            },
        }


# ─── Detection ──────────────────────────────────────────────────────────────

def detect_pose(
    image_path: str | Path | np.ndarray,
    min_detection_confidence: float = 0.5,
) -> PoseResult | None:
    """Detect pose landmarks in a single image.

    Args:
        image_path: Path to image OR a BGR numpy image.
        min_detection_confidence: Minimum confidence for pose detection.

    Returns:
        PoseResult or None if no pose detected.
    """
    if isinstance(image_path, np.ndarray):
        img = image_path
    else:
        img = cv2.imread(str(image_path))
        if img is None:
            raise FileNotFoundError(f"Image not found: {image_path}")

    h, w = img.shape[:2]
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    with mp_pose.Pose(
        static_image_mode=True,
        min_detection_confidence=min_detection_confidence,
        model_complexity=1,  # 0=lite, 1=full, 2=heavy (heavy downloads model on demand)
    ) as pose:
        results = pose.process(rgb)

    if not results.pose_landmarks:
        return None

    landmarks = []
    for idx, lm in enumerate(results.pose_landmarks.landmark):
        landmarks.append(Landmark(
            index=idx,
            name=LANDMARK_NAMES.get(idx, f"LM_{idx}"),
            x=lm.x * w,
            y=lm.y * h,
            z=lm.z * w,
            visibility=lm.visibility,
        ))

    # Compute average visibility of key landmarks as detection confidence
    key_vis = [lm.visibility for lm in landmarks if lm.index in [l.value for l in ALL_KEY_LANDMARKS]]
    avg_confidence = sum(key_vis) / len(key_vis) if key_vis else 0.0

    return PoseResult(
        landmarks=landmarks,
        image_width=w,
        image_height=h,
        detection_confidence=avg_confidence,
    )


def render_pose_stick_figure(
    pose_result: PoseResult,
    output_size: tuple[int, int] | None = None,
    thickness: int = 6,
    bg_color: tuple[int, int, int] = (0, 0, 0),
) -> np.ndarray:
    """Render a pose stick figure from MediaPipe landmarks.

    Creates an OpenPose-style conditioning image that can be used as an
    additional IP-Adapter reference to preserve body structure.

    Args:
        pose_result: PoseResult from detect_pose().
        output_size: (width, height) for output image. Defaults to pose image size.
        thickness: Line thickness for limbs.
        bg_color: Background color (BGR).

    Returns:
        BGR numpy image with pose stick figure.
    """
    w, h = output_size or (pose_result.image_width, pose_result.image_height)
    canvas = np.full((h, w, 3), bg_color, dtype=np.uint8)

    def get(lm_enum: mp_pose.PoseLandmark) -> Landmark | None:
        lm = pose_result.landmarks[lm_enum.value]
        return lm if lm.visibility > 0.5 else None

    def pt(lm_enum: mp_pose.PoseLandmark) -> tuple[int, int] | None:
        lm = get(lm_enum)
        if lm is None:
            return None
        return (int(lm.x * w / pose_result.image_width), int(lm.y * h / pose_result.image_height))

    def line(p1, p2, color, t=thickness):
        if p1 is not None and p2 is not None:
            cv2.line(canvas, p1, p2, color, t, cv2.LINE_AA)

    def circle(center, color, radius=8):
        if center is not None:
            cv2.circle(canvas, center, radius, color, -1, cv2.LINE_AA)

    # Colors (BGR)
    c_head = (0, 255, 255)      # yellow
    c_torso = (0, 255, 0)       # green
    c_arm_l = (255, 0, 0)       # blue
    c_arm_r = (0, 0, 255)       # red
    c_leg_l = (255, 255, 0)     # cyan
    c_leg_r = (255, 0, 255)     # magenta

    nose = pt(mp_pose.PoseLandmark.NOSE)
    left_ear = pt(mp_pose.PoseLandmark.LEFT_EAR)
    right_ear = pt(mp_pose.PoseLandmark.RIGHT_EAR)
    left_eye = pt(mp_pose.PoseLandmark.LEFT_EYE)
    right_eye = pt(mp_pose.PoseLandmark.RIGHT_EYE)
    mouth = pt(mp_pose.PoseLandmark.MOUTH_LEFT)

    # Head circle approximation
    if nose is not None and left_ear is not None and right_ear is not None:
        head_radius = max(10, int(abs(left_ear[0] - right_ear[0]) * 0.7))
        cv2.circle(canvas, nose, head_radius, c_head, thickness, cv2.LINE_AA)
        circle(nose, c_head, radius=5)
    elif nose is not None:
        circle(nose, c_head, radius=10)

    # Torso
    ls = pt(mp_pose.PoseLandmark.LEFT_SHOULDER)
    rs = pt(mp_pose.PoseLandmark.RIGHT_SHOULDER)
    lh = pt(mp_pose.PoseLandmark.LEFT_HIP)
    rh = pt(mp_pose.PoseLandmark.RIGHT_HIP)
    line(ls, rs, c_torso)
    line(lh, rh, c_torso)
    line(ls, lh, c_torso)
    line(rs, rh, c_torso)

    # Arms
    le = pt(mp_pose.PoseLandmark.LEFT_ELBOW)
    lw = pt(mp_pose.PoseLandmark.LEFT_WRIST)
    line(ls, le, c_arm_l)
    line(le, lw, c_arm_l)

    re = pt(mp_pose.PoseLandmark.RIGHT_ELBOW)
    rw = pt(mp_pose.PoseLandmark.RIGHT_WRIST)
    line(rs, re, c_arm_r)
    line(re, rw, c_arm_r)

    # Legs
    lk = pt(mp_pose.PoseLandmark.LEFT_KNEE)
    la = pt(mp_pose.PoseLandmark.LEFT_ANKLE)
    line(lh, lk, c_leg_l)
    line(lk, la, c_leg_l)

    rk = pt(mp_pose.PoseLandmark.RIGHT_KNEE)
    ra = pt(mp_pose.PoseLandmark.RIGHT_ANKLE)
    line(rh, rk, c_leg_r)
    line(rk, ra, c_leg_r)

    # Joints
    for p in [ls, rs, le, re, lw, rw, lh, rh, lk, rk, la, ra]:
        circle(p, (255, 255, 255), radius=thickness)

    return canvas


def detect_pose_multi(
    image_path: str | Path,
    runs: int = 1,
    min_detection_confidence: float = 0.5,
) -> PoseResult | None:
    """Detect pose with multiple runs and average landmarks for stability.

    Args:
        image_path: Path to image
        runs: Number of detection runs to average (1=single, 3=averaged)
        min_detection_confidence: Minimum detection confidence

    Returns:
        PoseResult with averaged landmarks, or None if no pose detected
    """
    if runs <= 1:
        return detect_pose(image_path, min_detection_confidence)

    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(f"Image not found: {image_path}")

    h, w = img.shape[:2]
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    all_landmarks = []

    for _ in range(runs):
        with mp_pose.Pose(
            static_image_mode=True,
            min_detection_confidence=min_detection_confidence,
            model_complexity=1,
        ) as pose:
            results = pose.process(rgb)

        if not results.pose_landmarks:
            return None

        run_lms = []
        for idx, lm in enumerate(results.pose_landmarks.landmark):
            run_lms.append({
                'x': lm.x * w,
                'y': lm.y * h,
                'z': lm.z * w,
                'visibility': lm.visibility,
            })
        all_landmarks.append(run_lms)

    # Average landmarks across runs
    averaged = []
    for idx in range(len(all_landmarks[0])):
        avg_x = np.mean([run[idx]['x'] for run in all_landmarks])
        avg_y = np.mean([run[idx]['y'] for run in all_landmarks])
        avg_z = np.mean([run[idx]['z'] for run in all_landmarks])
        avg_vis = np.mean([run[idx]['visibility'] for run in all_landmarks])
        averaged.append(Landmark(
            index=idx,
            name=LANDMARK_NAMES.get(idx, f"LM_{idx}"),
            x=float(avg_x),
            y=float(avg_y),
            z=float(avg_z),
            visibility=float(avg_vis),
        ))

    key_vis = [lm.visibility for lm in averaged if lm.index in [l.value for l in ALL_KEY_LANDMARKS]]
    avg_confidence = sum(key_vis) / len(key_vis) if key_vis else 0.0

    return PoseResult(
        landmarks=averaged,
        image_width=w,
        image_height=h,
        detection_confidence=avg_confidence,
    )


# ─── Comparison ─────────────────────────────────────────────────────────────

def _get_group(landmark: mp_pose.PoseLandmark) -> str:
    if landmark in HEAD_LANDMARKS:
        return "HEAD"
    elif landmark in TORSO_LANDMARKS:
        return "TORSO"
    elif landmark in LIMB_LANDMARKS:
        return "LIMB"
    return "OTHER"


def compare_poses(
    original: PoseResult,
    inpainted: PoseResult,
    head_threshold_pct: float = 0.3,
    torso_threshold_pct: float = 0.5,
    limbs_threshold_pct: float = 1.5,
    strict: bool = False,
    strict_threshold_pct: float = 0.1,
) -> PoseComparison:
    """Compare two poses and determine if the pose changed.

    Args:
        head_threshold_pct: Head change threshold (default 0.3%)
        torso_threshold_pct: Torso change threshold (default 0.5%)
        limbs_threshold_pct: Limbs change threshold (default 1.5%)
        strict: If True, any landmark > strict_threshold_pct = POSE_CHANGED
        strict_threshold_pct: Per-landmark threshold in strict mode (default 0.1%)
    """
    diffs = []
    diagonal = (original.diagonal + inpainted.diagonal) / 2

    for lm_enum in ALL_KEY_LANDMARKS:
        idx = lm_enum.value
        lm1 = original.landmarks[idx]
        lm2 = inpainted.landmarks[idx]

        dx = lm2.x - lm1.x
        dy = lm2.y - lm1.y
        distance = math.sqrt(dx ** 2 + dy ** 2)
        distance_pct = (distance / diagonal) * 100

        diffs.append(LandmarkDiff(
            landmark=lm_enum,
            name=lm_enum.name,
            dx=dx,
            dy=dy,
            distance=distance,
            distance_normalized=distance_pct,
            group=_get_group(lm_enum),
        ))

    # Compute group averages
    head_diffs = [d for d in diffs if d.group == "HEAD"]
    torso_diffs = [d for d in diffs if d.group == "TORSO"]
    limb_diffs = [d for d in diffs if d.group == "LIMB"]

    head_avg = float(np.mean([d.distance_normalized for d in head_diffs])) if head_diffs else 0.0
    torso_avg = float(np.mean([d.distance_normalized for d in torso_diffs])) if torso_diffs else 0.0
    limbs_avg = float(np.mean([d.distance_normalized for d in limb_diffs])) if limb_diffs else 0.0

    # Check thresholds
    head_changed = head_avg > head_threshold_pct
    torso_changed = torso_avg > torso_threshold_pct
    limbs_changed = limbs_avg > limbs_threshold_pct

    # Strict mode: any single landmark above threshold = CHANGED
    if strict:
        max_landmark_pct = max(d.distance_normalized for d in diffs) if diffs else 0.0
        pose_changed = max_landmark_pct > strict_threshold_pct
    else:
        # Standard mode: head or torso changed = POSE_CHANGED
        pose_changed = head_changed or torso_changed

    # Confidence based on detection quality
    confidence = min(original.detection_confidence, inpainted.detection_confidence)

    # Build summary
    parts = []
    if head_changed:
        parts.append(f"HEAD changed ({head_avg:.1f}% > {head_threshold_pct}%)")
    else:
        parts.append(f"HEAD stable ({head_avg:.1f}%)")
    if torso_changed:
        parts.append(f"TORSO changed ({torso_avg:.1f}% > {torso_threshold_pct}%)")
    else:
        parts.append(f"TORSO stable ({torso_avg:.1f}%)")
    if limbs_changed:
        parts.append(f"LIMBS changed ({limbs_avg:.1f}% > {limbs_threshold_pct}%)")
    else:
        parts.append(f"LIMBS stable ({limbs_avg:.1f}%)")

    summary = " | ".join(parts)

    return PoseComparison(
        original=original,
        inpainted=inpainted,
        diffs=diffs,
        head_changed=head_changed,
        torso_changed=torso_changed,
        limbs_changed=limbs_changed,
        pose_changed=pose_changed,
        confidence=confidence,
        summary=summary,
    )


# ─── Angle Analysis ─────────────────────────────────────────────────────────

def _compute_angle(p1: Landmark, p2: Landmark, p3: Landmark) -> float:
    """Compute angle at p2 formed by p1-p2-p3."""
    v1 = (p1.x - p2.x, p1.y - p2.y)
    v2 = (p3.x - p2.x, p3.y - p2.y)
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    mag1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2)
    mag2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2)
    if mag1 == 0 or mag2 == 0:
        return 0.0
    cos_angle = max(-1, min(1, dot / (mag1 * mag2)))
    return math.degrees(math.acos(cos_angle))


def compute_joint_angles(pose: PoseResult) -> dict[str, float]:
    """Compute key joint angles for the pose."""
    lm = pose.landmarks
    return {
        "left_shoulder": _compute_angle(lm[23], lm[11], lm[13]),   # hip-shoulder-elbow
        "right_shoulder": _compute_angle(lm[24], lm[12], lm[14]),
        "left_elbow": _compute_angle(lm[11], lm[13], lm[15]),      # shoulder-elbow-wrist
        "right_elbow": _compute_angle(lm[12], lm[14], lm[16]),
        "neck_tilt": _compute_angle(lm[11], lm[0], lm[12]),         # shoulder-nose-shoulder
        "torso_lean": _compute_angle(
            Landmark(index=0, name="mid_shoulder", x=(lm[11].x + lm[12].x) / 2,
                     y=(lm[11].y + lm[12].y) / 2, z=0, visibility=1),
            Landmark(index=0, name="mid_hip", x=(lm[23].x + lm[24].x) / 2,
                     y=(lm[23].y + lm[24].y) / 2, z=0, visibility=1),
            lm[0],
        ),
    }


def compare_angles(original: PoseResult, inpainted: PoseResult, threshold_deg: float = 15.0) -> dict:
    """Compare joint angles between two poses."""
    angles1 = compute_joint_angles(original)
    angles2 = compute_joint_angles(inpainted)
    result = {}
    for joint in angles1:
        diff = abs(angles1[joint] - angles2[joint])
        result[joint] = {
            "original_deg": round(angles1[joint], 1),
            "inpainted_deg": round(angles2[joint], 1),
            "diff_deg": round(diff, 1),
            "changed": diff > threshold_deg,
        }
    return result


# ─── Visualization ──────────────────────────────────────────────────────────

def draw_pose(
    image_path: str | Path,
    pose: PoseResult,
    output_path: str | Path | None = None,
) -> np.ndarray:
    """Draw pose landmarks on image."""
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(f"Image not found: {image_path}")

    h, w = img.shape[:2]

    # Draw connections
    for connection in mp_pose.POSE_CONNECTIONS:
        start_idx = connection[0]
        end_idx = connection[1]
        if start_idx < len(pose.landmarks) and end_idx < len(pose.landmarks):
            lm1 = pose.landmarks[start_idx]
            lm2 = pose.landmarks[end_idx]
            if lm1.visibility > 0.5 and lm2.visibility > 0.5:
                pt1 = (int(lm1.x), int(lm1.y))
                pt2 = (int(lm2.x), int(lm2.y))
                cv2.line(img, pt1, pt2, (0, 255, 0), 2)

    # Draw landmarks
    for lm in pose.landmarks:
        if lm.visibility > 0.5:
            color = (0, 0, 255)  # red
            if lm.index in [l.value for l in HEAD_LANDMARKS]:
                color = (255, 0, 0)  # blue for head
            elif lm.index in [l.value for l in TORSO_LANDMARKS]:
                color = (0, 255, 0)  # green for torso
            cv2.circle(img, (int(lm.x), int(lm.y)), 4, color, -1)

    if output_path:
        cv2.imwrite(str(output_path), img)

    return img


def draw_comparison(
    original_path: str | Path,
    inpainted_path: str | Path,
    comparison: PoseComparison,
    output_path: str | Path,
):
    """Draw side-by-side comparison with difference lines."""
    img1 = cv2.imread(str(original_path))
    img2 = cv2.imread(str(inpainted_path))

    if img1 is None or img2 is None:
        raise FileNotFoundError("One or both images not found")

    h1, w1 = img1.shape[:2]
    h2, w2 = img2.shape[:2]

    # Resize to same height
    target_h = max(h1, h2)
    if h1 != target_h:
        img1 = cv2.resize(img1, (int(w1 * target_h / h1), target_h))
    if h2 != target_h:
        img2 = cv2.resize(img2, (int(w2 * target_h / h2), target_h))

    # Draw landmarks on both
    for lm in comparison.original.landmarks:
        if lm.visibility > 0.5:
            cv2.circle(img1, (int(lm.x), int(lm.y)), 3, (0, 255, 0), -1)

    for lm in comparison.inpainted.landmarks:
        if lm.visibility > 0.5:
            cv2.circle(img2, (int(lm.x), int(lm.y)), 3, (0, 255, 0), -1)

    # Draw difference arrows for changed landmarks
    for diff in comparison.diffs:
        if diff.distance_normalized > 2.0:  # Only show significant changes
            idx = diff.landmark.value
            lm1 = comparison.original.landmarks[idx]
            lm2 = comparison.inpainted.landmarks[idx]

            # Arrow on original (where it was)
            cv2.arrowedLine(
                img1,
                (int(lm1.x), int(lm1.y)),
                (int(lm2.x), int(lm2.y)),
                (0, 0, 255), 2, tipLength=0.3,
            )
            # Arrow on inpainted (where it moved to)
            cv2.arrowedLine(
                img2,
                (int(lm1.x), int(lm1.y)),
                (int(lm2.x), int(lm2.y)),
                (0, 0, 255), 2, tipLength=0.3,
            )

    # Concatenate side by side
    combined = np.hstack([img1, img2])

    # Add status text
    status = "POSE CHANGED" if comparison.pose_changed else "POSE SAME"
    color = (0, 0, 255) if comparison.pose_changed else (0, 255, 0)
    cv2.putText(combined, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
    cv2.putText(
        combined,
        f"Confidence: {comparison.confidence:.1%}",
        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2,
    )

    cv2.imwrite(str(output_path), combined)
    return combined


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Pose Detection & Comparison for SE11 NSFW Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --original pose1.png --inpainted pose2.png
  %(prog)s --original pose1.png --inpainted pose2.png --strict
  %(prog)s --original pose1.png --inpainted pose2.png --runs 3 --verbose
  %(prog)s --detect pose1.png
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # detect command
    detect_parser = subparsers.add_parser("detect", help="Detect pose in a single image")
    detect_parser.add_argument("image", help="Path to image")
    detect_parser.add_argument("--runs", type=int, default=1, help="Number of detection runs to average")

    # compare command (default)
    parser.add_argument("--original", "-o", help="Path to original image")
    parser.add_argument("--inpainted", "-i", help="Path to inpainted image")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--visualize", action="store_true", help="Generate visualization")
    parser.add_argument("--output", help="Output path for visualization")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Strict mode
    parser.add_argument("--strict", action="store_true",
                        help="Zero tolerance: any landmark > 0.1%% = POSE_CHANGED")
    parser.add_argument("--strict-threshold", type=float, default=0.1,
                        help="Per-landmark threshold for strict mode (default: 0.1%%)")

    # Multi-run averaging
    parser.add_argument("--runs", type=int, default=1,
                        help="Number of detection runs to average (default: 1)")

    # Thresholds
    parser.add_argument("--head-threshold", type=float, default=0.3,
                        help="Head change threshold %% (default: 0.3)")
    parser.add_argument("--torso-threshold", type=float, default=0.5,
                        help="Torso change threshold %% (default: 0.5)")
    parser.add_argument("--limbs-threshold", type=float, default=1.5,
                        help="Limbs change threshold %% (default: 1.5)")

    args = parser.parse_args()

    # Handle detect subcommand
    if args.command == "detect":
        runs = getattr(args, 'runs', 1)
        pose = detect_pose_multi(args.image, runs=runs) if runs > 1 else detect_pose(args.image)
        if pose is None:
            print(f"No pose detected in {args.image}")
            sys.exit(1)
        print(f"Detected {len(pose.landmarks)} landmarks in {args.image}")
        print(f"Image: {pose.image_width}x{pose.image_height}, diagonal: {pose.diagonal:.0f}px")
        print(f"Detection confidence: {pose.detection_confidence:.1%}")
        if runs > 1:
            print(f"Runs averaged: {runs}")
        angles = compute_joint_angles(pose)
        print("\nJoint angles:")
        for joint, angle in angles.items():
            print(f"  {joint}: {angle:.1f}°")
        return

    # Handle compare (default)
    if not args.original or not args.inpainted:
        parser.error("--original and --inpainted are required for comparison")

    if not args.json:
        print(f"Detecting poses...")
    original = detect_pose_multi(args.original, runs=args.runs) if args.runs > 1 else detect_pose(args.original)
    inpainted = detect_pose_multi(args.inpainted, runs=args.runs) if args.runs > 1 else detect_pose(args.inpainted)

    if original is None:
        if args.json:
            print(json.dumps({"error": f"No pose detected in {args.original}"}))
        else:
            print(f"No pose detected in {args.original}")
        sys.exit(1)
    if inpainted is None:
        if args.json:
            print(json.dumps({"error": f"No pose detected in {args.inpainted}"}))
        else:
            print(f"No pose detected in {args.inpainted}")
        sys.exit(1)

    if not args.json:
        print(f"Original: {len(original.landmarks)} landmarks ({original.image_width}x{original.image_height})")
        print(f"Inpainted: {len(inpainted.landmarks)} landmarks ({inpainted.image_width}x{inpainted.image_height})")

    comparison = compare_poses(
        original, inpainted,
        head_threshold_pct=args.head_threshold,
        torso_threshold_pct=args.torso_threshold,
        limbs_threshold_pct=args.limbs_threshold,
        strict=args.strict,
        strict_threshold_pct=args.strict_threshold,
    )

    # Angle comparison
    angle_diffs = compare_angles(original, inpainted)

    if args.json:
        output = comparison.to_dict()
        output["strict_mode"] = args.strict
        output["runs_averaged"] = args.runs
        # Convert numpy/native types in angle_diffs
        output["joint_angles"] = {
            k: {kk: (bool(vv) if kk == "changed" else round(float(vv), 1))
                for kk, vv in v.items()}
            for k, v in angle_diffs.items()
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"POSE COMPARISON RESULT")
        print(f"{'='*60}")
        if args.strict:
            print(f"Mode: STRICT (zero tolerance)")
        print(f"Status: {'POSE CHANGED' if comparison.pose_changed else 'POSE SAME'}")
        print(f"Confidence: {comparison.confidence:.1%}")
        print(f"Summary: {comparison.summary}")

        if args.verbose:
            print(f"\n--- Per-Landmark Differences ---")
            print(f"{'Landmark':<20} {'Dist (px)':>10} {'Dist (%)':>10} {'Group':>8}")
            print(f"{'-'*50}")
            for d in sorted(comparison.diffs, key=lambda x: x.distance_normalized, reverse=True):
                marker = " *" if d.distance_normalized > (args.strict_threshold if args.strict else 3.0) else ""
                print(f"{d.name:<20} {d.distance:>10.1f} {d.distance_normalized:>9.2f}% {d.group:>8}{marker}")

            print(f"\n--- Joint Angle Differences ---")
            for joint, info in angle_diffs.items():
                marker = " *" if info["changed"] else ""
                print(f"{joint:<20} {info['original_deg']:>6.1f}° → {info['inpainted_deg']:>6.1f}° (Δ {info['diff_deg']:.1f}°){marker}")

    if args.visualize:
        output_path = args.output or "pose_comparison.png"
        draw_comparison(args.original, args.inpainted, comparison, output_path)
        if not args.json:
            print(f"\nVisualization saved to: {output_path}")

    sys.exit(1 if comparison.pose_changed else 0)


if __name__ == "__main__":
    main()
