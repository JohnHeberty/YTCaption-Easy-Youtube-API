#!/usr/bin/env python3
"""
pose_detector.py — Pose Detection & Comparison for SE11 NSFW Pipeline

Detects body poses using DWPose (130 keypoints: 18 body + 21+21 hands + 70 face)
and compares them to determine if the pose changed between original and output.

DWPose uses YOLOX for person detection + RTMPose for body/hand/face estimation.
Much more precise than MediaPipe (33 landmarks): detects hands, fingers, and face contour.

Usage:
    python pose_detector.py --original pose1.png --inpainted pose2.png
    python pose_detector.py --detect pose1.png

Dependencies:
    dwpose
    opencv-python-headless
    numpy
    scipy
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# Suppress DWPose/HuggingFace warnings
import logging
logging.getLogger("dwpose").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning, module="dwpose")

# Lazy-load DWPose detector (heavy, downloaded on first use)
_detector = None


def _get_detector():
    """Lazy-load DWPose detector."""
    global _detector
    if _detector is None:
        from dwpose import DwposeDetector
        _detector = DwposeDetector.from_pretrained_default(torchscript_device="cpu")
    return _detector


# ─── DWPose Body Keypoint Layout (18, OpenPose COCO) ──────────────────────
# 0:Nose, 1:Neck, 2:RShoulder, 3:RElbow, 4:RWrist, 5:LShoulder, 6:LElbow, 7:LWrist
# 8:RHip, 9:RKnee, 10:RAnkle, 11:LHip, 12:LKnee, 13:LAnkle
# 14:REye, 15:LEye, 16:REar, 17:LEar

BODY_NAMES = [
    "NOSE", "NECK", "R_SHOULDER", "R_ELBOW", "R_WRIST",
    "L_SHOULDER", "L_ELBOW", "L_WRIST", "R_HIP", "R_KNEE",
    "R_ANKLE", "L_HIP", "L_KNEE", "L_ANKLE", "R_EYE",
    "L_EYE", "R_EAR", "L_EAR",
]

# ─── Landmark Groups ────────────────────────────────────────────────────────

HEAD_BODY_INDICES = [0, 14, 15, 16, 17]   # Nose, REye, LEye, REar, LEar
TORSO_BODY_INDICES = [1, 2, 5, 8, 11]     # Neck, RShoulder, LShoulder, RHip, LHip
LIMB_BODY_INDICES = [3, 4, 6, 7, 9, 10, 12, 13]  # Elbows, Wrists, Knees, Ankles


# ─── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class Landmark:
    """Single body landmark with position and confidence."""
    index: int
    name: str
    x: float  # pixel coordinates
    y: float
    z: float  # relative depth (0 for DWPose)
    visibility: float  # 0-1 confidence (score from DWPose)
    group: str = ""  # HEAD, TORSO, LIMB, HAND_LEFT, HAND_RIGHT, FACE


@dataclass
class PoseResult:
    """Complete pose detection result for one image."""
    landmarks: list[Landmark]
    hand_left_landmarks: list[Landmark]
    hand_right_landmarks: list[Landmark]
    face_landmarks: list[Landmark]
    image_width: int
    image_height: int
    detection_confidence: float

    @property
    def diagonal(self) -> float:
        return math.sqrt(self.image_width ** 2 + self.image_height ** 2)

    def to_dict(self) -> dict:
        visible = [lm for lm in self.landmarks if lm.visibility > 0.3]
        hands_l = [lm for lm in self.hand_left_landmarks if lm.visibility > 0.3]
        hands_r = [lm for lm in self.hand_right_landmarks if lm.visibility > 0.3]
        face_vis = [lm for lm in self.face_landmarks if lm.visibility > 0.3]
        return {
            "image_size": [self.image_width, self.image_height],
            "diagonal": round(self.diagonal, 1),
            "detection_confidence": round(self.detection_confidence, 3),
            "body_landmarks": len(visible),
            "hand_left_landmarks": len(hands_l),
            "hand_right_landmarks": len(hands_r),
            "face_landmarks": len(face_vis),
            "total_landmarks": len(visible) + len(hands_l) + len(hands_r) + len(face_vis),
        }


@dataclass
class LandmarkDiff:
    """Difference for a single landmark between two poses."""
    landmark_index: int
    name: str
    dx: float
    dy: float
    distance: float
    distance_normalized: float  # as % of image diagonal
    group: str  # HEAD, TORSO, LIMB, HAND_LEFT, HAND_RIGHT, FACE


@dataclass
class PoseComparison:
    """Complete comparison result between two poses."""
    original: PoseResult
    inpainted: PoseResult
    diffs: list[LandmarkDiff]
    head_changed: bool
    torso_changed: bool
    limbs_changed: bool
    hands_changed: bool
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
            "hands_changed": bool(self.hands_changed),
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
    """Detect pose landmarks in a single image using DWPose.

    Detects body (18), hands (21+21), and face (70) keypoints.

    Args:
        image_path: Path to image OR a BGR numpy image.
        min_detection_confidence: Minimum confidence for body detection.

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

    detector = _get_detector()

    # DWPose detect_poses returns PoseResult(body, left_hand, right_hand, face)
    poses = detector.detect_poses(rgb)

    if not poses:
        return None

    # Take the first (most confident) person
    pose = poses[0]

    landmarks = []
    hand_left = []
    hand_right = []
    face_lms = []

    # Body keypoints (18)
    for idx, kp in enumerate(pose.body.keypoints):
        if kp is None:
            continue
        if kp.score < min_detection_confidence * 0.5:
            continue
        name = BODY_NAMES[idx] if idx < len(BODY_NAMES) else f"BODY_{idx}"
        if idx in HEAD_BODY_INDICES:
            group = "HEAD"
        elif idx in TORSO_BODY_INDICES:
            group = "TORSO"
        elif idx in LIMB_BODY_INDICES:
            group = "LIMB"
        else:
            group = "OTHER"
        landmarks.append(Landmark(
            index=idx, name=name,
            x=kp.x, y=kp.y, z=0.0,
            visibility=kp.score, group=group,
        ))

    # Left hand (21)
    if pose.left_hand:
        for idx, kp in enumerate(pose.left_hand):
            if kp is None:
                continue
            hand_left.append(Landmark(
                index=idx, name=f"L_HAND_{idx}",
                x=kp.x, y=kp.y, z=0.0,
                visibility=kp.score, group="HAND_LEFT",
            ))

    # Right hand (21)
    if pose.right_hand:
        for idx, kp in enumerate(pose.right_hand):
            if kp is None:
                continue
            hand_right.append(Landmark(
                index=idx, name=f"R_HAND_{idx}",
                x=kp.x, y=kp.y, z=0.0,
                visibility=kp.score, group="HAND_RIGHT",
            ))

    # Face (70)
    if pose.face:
        for idx, kp in enumerate(pose.face):
            if kp is None:
                continue
            face_lms.append(Landmark(
                index=idx, name=f"FACE_{idx}",
                x=kp.x, y=kp.y, z=0.0,
                visibility=kp.score, group="FACE",
            ))

    # Compute average visibility of body landmarks as detection confidence
    key_vis = [lm.visibility for lm in landmarks]
    avg_confidence = sum(key_vis) / len(key_vis) if key_vis else 0.0

    all_lm = landmarks + hand_left + hand_right + face_lms
    return PoseResult(
        landmarks=landmarks,
        hand_left_landmarks=hand_left,
        hand_right_landmarks=hand_right,
        face_landmarks=face_lms,
        image_width=w,
        image_height=h,
        detection_confidence=avg_confidence,
    )


def detect_all_poses(
    image: np.ndarray,
    min_detection_confidence: float = 0.3,
) -> list[PoseResult]:
    """Detect ALL poses in the image (multi-person support).

    Unlike detect_pose which returns only the first/most confident person,
    this returns all detected poses sorted by confidence descending.

    Args:
        image: BGR or RGB image.
        min_detection_confidence: Minimum keypoint confidence threshold.

    Returns:
        List of PoseResult objects, sorted by detection_confidence descending.
        Empty list if no poses detected.
    """
    from ..app.services.dwpose import DWposeDetector

    detector = DWposeDetector()

    rgb = image
    if len(image.shape) == 3 and image.shape[2] == 3:
        # Assume BGR, convert to RGB
        rgb = image[:, :, ::-1].copy()

    poses = detector.detect_poses(rgb)
    if not poses:
        return []

    results = []
    h, w = image.shape[:2]

    for pose in poses:
        landmarks = []
        hand_left = []
        hand_right = []
        face_lms = []

        for idx, kp in enumerate(pose.body.keypoints):
            if kp is None:
                continue
            if kp.score < min_detection_confidence * 0.5:
                continue
            landmarks.append(Landmark(
                x=kp.x / w, y=kp.y / h, visibility=kp.score,
                group=POSE_CONNECTIONS.get(idx, ("BODY",))[0] if idx < 18 else "BODY",
            ))

        # Hands
        if pose.left_hand is not None:
            for kp in pose.left_hand.keypoints:
                if kp is not None and kp.score >= min_detection_confidence * 0.3:
                    hand_left.append(Landmark(x=kp.x/w, y=kp.y/h, visibility=kp.score, group="HAND_LEFT"))

        if pose.right_hand is not None:
            for kp in pose.right_hand.keypoints:
                if kp is not None and kp.score >= min_detection_confidence * 0.3:
                    hand_right.append(Landmark(x=kp.x/w, y=kp.y/h, visibility=kp.score, group="HAND_RIGHT"))

        if pose.face is not None:
            for kp in pose.face.keypoints:
                if kp is not None and kp.score >= min_detection_confidence * 0.3:
                    face_lms.append(Landmark(x=kp.x/w, y=kp.y/h, visibility=kp.score, group="FACE"))

        key_vis = [lm.visibility for lm in landmarks]
        avg_confidence = sum(key_vis) / len(key_vis) if key_vis else 0.0

        results.append(PoseResult(
            landmarks=landmarks,
            hand_left_landmarks=hand_left,
            hand_right_landmarks=hand_right,
            face_landmarks=face_lms,
            image_width=w,
            image_height=h,
            detection_confidence=avg_confidence,
        ))

    # Sort by confidence descending
    results.sort(key=lambda r: r.detection_confidence, reverse=True)
    return results


def render_pose_stick_figure(
    pose_result: PoseResult,
    output_size: tuple[int, int] | None = None,
    thickness: int = 6,
    bg_color: tuple[int, int, int] = (0, 0, 0),
) -> np.ndarray:
    """Render a pose stick figure from DWPose body landmarks.

    Creates an OpenPose-style conditioning image (18-body COCO format).

    Args:
        pose_result: PoseResult from detect_pose().
        output_size: (width, height) for output image.
        thickness: Line thickness for limbs.
        bg_color: Background color (BGR).

    Returns:
        BGR numpy image with pose stick figure.
    """
    w, h = output_size or (pose_result.image_width, pose_result.image_height)
    canvas = np.full((h, w, 3), bg_color, dtype=np.uint8)

    # Build a quick lookup from body index → pixel position
    body_px = {}
    scale_x = w / pose_result.image_width
    scale_y = h / pose_result.image_height
    for lm in pose_result.landmarks:
        if lm.group in ("HEAD", "TORSO", "LIMB", "OTHER") and lm.visibility > 0.3:
            body_px[lm.index] = (int(lm.x * scale_x), int(lm.y * scale_y))

    def pt(idx: int):
        return body_px.get(idx)

    def line(p1, p2, color):
        if p1 is not None and p2 is not None:
            cv2.line(canvas, p1, p2, color, thickness, cv2.LINE_AA)

    def circle(center, color, radius=8):
        if center is not None:
            cv2.circle(canvas, center, radius, color, -1, cv2.LINE_AA)

    # Colors (BGR)
    c_head = (0, 255, 255)      # yellow
    c_torso = (0, 255, 0)       # green
    c_arm_r = (255, 0, 0)       # blue
    c_arm_l = (0, 0, 255)       # red
    c_leg_r = (255, 255, 0)     # cyan
    c_leg_l = (255, 0, 255)     # magenta

    # Head circle
    nose = pt(0)
    r_ear = pt(16)
    l_ear = pt(17)
    if nose is not None and r_ear is not None and l_ear is not None:
        head_radius = max(10, int(abs(l_ear[0] - r_ear[0]) * 0.7))
        cv2.circle(canvas, nose, head_radius, c_head, thickness, cv2.LINE_AA)
        circle(nose, c_head, radius=5)
    elif nose is not None:
        circle(nose, c_head, radius=10)

    # Torso
    neck = pt(1)
    r_shoulder = pt(2)
    l_shoulder = pt(5)
    r_hip = pt(8)
    l_hip = pt(11)
    line(r_shoulder, l_shoulder, c_torso)
    line(r_hip, l_hip, c_torso)
    line(r_shoulder, r_hip, c_torso)
    line(l_shoulder, l_hip, c_torso)

    # Right arm
    r_elbow = pt(3)
    r_wrist = pt(4)
    line(r_shoulder, r_elbow, c_arm_r)
    line(r_elbow, r_wrist, c_arm_r)

    # Left arm
    l_elbow = pt(6)
    l_wrist = pt(7)
    line(l_shoulder, l_elbow, c_arm_l)
    line(l_elbow, l_wrist, c_arm_l)

    # Right leg
    r_knee = pt(9)
    r_ankle = pt(10)
    line(r_hip, r_knee, c_leg_r)
    line(r_knee, r_ankle, c_leg_r)

    # Left leg
    l_knee = pt(12)
    l_ankle = pt(13)
    line(l_hip, l_knee, c_leg_l)
    line(l_knee, l_ankle, c_leg_l)

    # Joints
    for p in [r_shoulder, l_shoulder, r_elbow, l_elbow, r_wrist, l_wrist,
              r_hip, l_hip, r_knee, l_knee, r_ankle, l_ankle]:
        circle(p, (255, 255, 255), radius=thickness)

    return canvas


# ─── Comparison ─────────────────────────────────────────────────────────────

def _find_body_lm(pose: PoseResult, body_index: int) -> Landmark | None:
    """Find a body landmark by its DWPose body index."""
    for lm in pose.landmarks:
        if lm.index == body_index and lm.group in ("HEAD", "TORSO", "LIMB", "OTHER"):
            return lm
    return None


def _find_hand_lm(pose: PoseResult, hand: str, hand_index: int) -> Landmark | None:
    """Find a hand landmark by index."""
    targets = pose.hand_left_landmarks if hand == "left" else pose.hand_right_landmarks
    for lm in targets:
        if lm.index == hand_index:
            return lm
    return None


def compare_poses(
    original: PoseResult,
    inpainted: PoseResult,
    head_threshold_pct: float = 0.3,
    torso_threshold_pct: float = 0.5,
    limbs_threshold_pct: float = 1.5,
    hands_threshold_pct: float = 1.5,
    strict: bool = False,
    strict_threshold_pct: float = 0.1,
) -> PoseComparison:
    """Compare two poses and determine if the pose changed.

    Now includes hands in the comparison. pose_changed = head OR torso OR limbs OR hands.

    Args:
        head_threshold_pct: Head change threshold (default 0.3%)
        torso_threshold_pct: Torso change threshold (default 0.5%)
        limbs_threshold_pct: Limbs change threshold (default 1.5%)
        hands_threshold_pct: Hands change threshold (default 1.5%)
        strict: If True, any landmark > strict_threshold_pct = POSE_CHANGED
        strict_threshold_pct: Per-landmark threshold in strict mode (default 0.1%)
    """
    diffs = []
    diagonal = (original.diagonal + inpainted.diagonal) / 2
    if diagonal == 0:
        diagonal = 1.0

    # ─── Body keypoint comparison ───
    for body_idx in range(18):
        lm1 = _find_body_lm(original, body_idx)
        lm2 = _find_body_lm(inpainted, body_idx)
        if lm1 is None or lm2 is None:
            continue

        dx = lm2.x - lm1.x
        dy = lm2.y - lm1.y
        distance = math.sqrt(dx ** 2 + dy ** 2)
        distance_pct = (distance / diagonal) * 100

        name = BODY_NAMES[body_idx] if body_idx < len(BODY_NAMES) else f"BODY_{body_idx}"
        diffs.append(LandmarkDiff(
            landmark_index=body_idx, name=name,
            dx=dx, dy=dy, distance=distance,
            distance_normalized=distance_pct, group=lm1.group,
        ))

    # ─── Hand keypoint comparison ───
    # Average hand displacement as a single metric
    def _avg_hand_diff(hand_lm1: list[Landmark], hand_lm2: list[Landmark], group: str) -> float | None:
        if not hand_lm1 or not hand_lm2:
            return None
        # Match by index
        matched = []
        for lm1 in hand_lm1:
            for lm2 in hand_lm2:
                if lm1.index == lm2.index:
                    matched.append((lm1, lm2))
                    break
        if not matched:
            return None
        total = 0.0
        for lm1, lm2 in matched:
            dx = lm2.x - lm1.x
            dy = lm2.y - lm1.y
            dist = math.sqrt(dx ** 2 + dy ** 2)
            dist_pct = (dist / diagonal) * 100
            total += dist_pct
            name = lm1.name
            diffs.append(LandmarkDiff(
                landmark_index=lm1.index, name=name,
                dx=dx, dy=dy, distance=dist,
                distance_normalized=dist_pct, group=group,
            ))
        return total / len(matched)

    left_hand_avg = _avg_hand_diff(
        original.hand_left_landmarks, inpainted.hand_left_landmarks, "HAND_LEFT")
    right_hand_avg = _avg_hand_diff(
        original.hand_right_landmarks, inpainted.hand_right_landmarks, "HAND_RIGHT")

    # ─── Group averages ───
    head_diffs = [d for d in diffs if d.group == "HEAD"]
    torso_diffs = [d for d in diffs if d.group == "TORSO"]
    limb_diffs = [d for d in diffs if d.group == "LIMB"]
    hand_diffs = [d for d in diffs if d.group in ("HAND_LEFT", "HAND_RIGHT")]

    head_avg = float(np.mean([d.distance_normalized for d in head_diffs])) if head_diffs else 0.0
    torso_avg = float(np.mean([d.distance_normalized for d in torso_diffs])) if torso_diffs else 0.0
    limbs_avg = float(np.mean([d.distance_normalized for d in limb_diffs])) if limb_diffs else 0.0

    # Hands average: combine left + right
    hand_avgs = []
    if left_hand_avg is not None:
        hand_avgs.append(left_hand_avg)
    if right_hand_avg is not None:
        hand_avgs.append(right_hand_avg)
    hands_avg = float(np.mean(hand_avgs)) if hand_avgs else 0.0

    # ─── Threshold checks ───
    head_changed = head_avg > head_threshold_pct
    torso_changed = torso_avg > torso_threshold_pct
    limbs_changed = limbs_avg > limbs_threshold_pct
    hands_changed = hands_avg > hands_threshold_pct

    if strict:
        max_landmark_pct = max(d.distance_normalized for d in diffs) if diffs else 0.0
        pose_changed = max_landmark_pct > strict_threshold_pct
    else:
        # pose_changed = ANY body region changed
        pose_changed = head_changed or torso_changed or limbs_changed or hands_changed

    confidence = min(original.detection_confidence, inpainted.detection_confidence)

    # Build summary
    parts = []
    parts.append(f"HEAD {'changed' if head_changed else 'stable'} ({head_avg:.1f}%)")
    parts.append(f"TORSO {'changed' if torso_changed else 'stable'} ({torso_avg:.1f}%)")
    parts.append(f"LIMBS {'changed' if limbs_changed else 'stable'} ({limbs_avg:.1f}%)")
    if hand_avgs:
        parts.append(f"HANDS {'changed' if hands_changed else 'stable'} ({hands_avg:.1f}%)")
    else:
        parts.append("HANDS (no data)")
    summary = " | ".join(parts)

    return PoseComparison(
        original=original,
        inpainted=inpainted,
        diffs=diffs,
        head_changed=head_changed,
        torso_changed=torso_changed,
        limbs_changed=limbs_changed,
        hands_changed=hands_changed,
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
    """Compute key joint angles for the pose using DWPose body indices."""
    # DWPose: 0=Nose, 1=Neck, 2=RShoulder, 3=RElbow, 4=RWrist
    # 5=LShoulder, 6=LElbow, 7=LWrist, 8=RHip, 11=LHip

    def get_or_zero(body_idx: int) -> Landmark:
        lm = _find_body_lm(pose, body_idx)
        return lm if lm is not None else Landmark(body_idx, "NONE", 0, 0, 0, 0)

    nose = get_or_zero(0)
    r_shoulder = get_or_zero(2)
    l_shoulder = get_or_zero(5)
    r_elbow = get_or_zero(3)
    l_elbow = get_or_zero(6)
    r_wrist = get_or_zero(4)
    l_wrist = get_or_zero(7)
    r_hip = get_or_zero(8)
    l_hip = get_or_zero(11)

    mid_shoulder = Landmark(0, "mid_shoulder",
                            x=(r_shoulder.x + l_shoulder.x) / 2,
                            y=(r_shoulder.y + l_shoulder.y) / 2, z=0, visibility=1)
    mid_hip = Landmark(0, "mid_hip",
                       x=(r_hip.x + l_hip.x) / 2,
                       y=(r_hip.y + l_hip.y) / 2, z=0, visibility=1)

    return {
        "right_shoulder": _compute_angle(r_hip, r_shoulder, r_elbow),
        "left_shoulder": _compute_angle(l_hip, l_shoulder, l_elbow),
        "right_elbow": _compute_angle(r_shoulder, r_elbow, r_wrist),
        "left_elbow": _compute_angle(l_shoulder, l_elbow, l_wrist),
        "neck_tilt": _compute_angle(r_shoulder, nose, l_shoulder),
        "torso_lean": _compute_angle(mid_shoulder, mid_hip, nose),
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
    scale_x = w / pose.image_width
    scale_y = h / pose.image_height

    # Draw body connections
    body_connections = [
        (0, 1),    # Nose-Neck
        (1, 2), (1, 5),   # Neck-Shoulders
        (2, 3), (3, 4),   # Right arm
        (5, 6), (6, 7),   # Left arm
        (1, 8), (1, 11),  # Neck-Hips
        (8, 9), (9, 10),  # Right leg
        (11, 12), (12, 13),  # Left leg
        (0, 14), (0, 15), (14, 16), (15, 17),  # Face
    ]

    body_px = {}
    for lm in pose.landmarks:
        if lm.visibility > 0.3:
            body_px[lm.index] = (int(lm.x * scale_x), int(lm.y * scale_y))

    for i, j in body_connections:
        p1 = body_px.get(i)
        p2 = body_px.get(j)
        if p1 and p2:
            cv2.line(img, p1, p2, (0, 255, 0), 2)

    # Draw body landmarks
    for lm in pose.landmarks:
        if lm.visibility > 0.3:
            color = (0, 0, 255)  # red
            if lm.group == "HEAD":
                color = (255, 0, 0)  # blue
            elif lm.group == "TORSO":
                color = (0, 255, 0)  # green
            cv2.circle(img, (int(lm.x * scale_x), int(lm.y * scale_y)), 4, color, -1)

    # Draw hand landmarks
    for lm in pose.hand_left_landmarks:
        if lm.visibility > 0.3:
            cv2.circle(img, (int(lm.x * scale_x), int(lm.y * scale_y)), 2, (0, 128, 255), -1)
    for lm in pose.hand_right_landmarks:
        if lm.visibility > 0.3:
            cv2.circle(img, (int(lm.x * scale_x), int(lm.y * scale_y)), 2, (255, 128, 0), -1)

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

    # Scale for landmark positions
    sx1 = img1.shape[1] / comparison.original.image_width
    sy1 = img1.shape[0] / comparison.original.image_height
    sx2 = img2.shape[1] / comparison.inpainted.image_width
    sy2 = img2.shape[0] / comparison.inpainted.image_height

    # Draw body landmarks on both
    for lm in comparison.original.landmarks:
        if lm.visibility > 0.3:
            cv2.circle(img1, (int(lm.x * sx1), int(lm.y * sy1)), 3, (0, 255, 0), -1)

    for lm in comparison.inpainted.landmarks:
        if lm.visibility > 0.3:
            cv2.circle(img2, (int(lm.x * sx2), int(lm.y * sy2)), 3, (0, 255, 0), -1)

    # Draw difference arrows for body landmarks
    for diff in comparison.diffs:
        if diff.group in ("HAND_LEFT", "HAND_RIGHT", "FACE"):
            continue
        if diff.distance_normalized > 2.0:
            idx = diff.landmark_index
            lm1 = None
            lm2 = None
            for lm in comparison.original.landmarks:
                if lm.index == idx and lm.group == diff.group:
                    lm1 = lm
                    break
            for lm in comparison.inpainted.landmarks:
                if lm.index == idx and lm.group == diff.group:
                    lm2 = lm
                    break
            if lm1 and lm2:
                cv2.arrowedLine(
                    img1,
                    (int(lm1.x * sx1), int(lm1.y * sy1)),
                    (int(lm2.x * sx2), int(lm2.y * sy2)),
                    (0, 0, 255), 2, tipLength=0.3,
                )
                cv2.arrowedLine(
                    img2,
                    (int(lm1.x * sx1), int(lm1.y * sy1)),
                    (int(lm2.x * sx2), int(lm2.y * sy2)),
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
        description="DWPose Detection & Comparison for SE11 NSFW Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # detect command
    detect_parser = subparsers.add_parser("detect", help="Detect pose in a single image")
    detect_parser.add_argument("image", help="Path to image")

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

    # Thresholds
    parser.add_argument("--head-threshold", type=float, default=0.3)
    parser.add_argument("--torso-threshold", type=float, default=0.5)
    parser.add_argument("--limbs-threshold", type=float, default=1.5)
    parser.add_argument("--hands-threshold", type=float, default=1.5)

    args = parser.parse_args()

    # Handle detect subcommand
    if args.command == "detect":
        pose = detect_pose(args.image)
        if pose is None:
            print(f"No pose detected in {args.image}")
            sys.exit(1)
        print(f"Detected {len(pose.landmarks)} body + {len(pose.hand_left_landmarks)} L-hand + "
              f"{len(pose.hand_right_landmarks)} R-hand + {len(pose.face_landmarks)} face landmarks")
        print(f"Image: {pose.image_width}x{pose.image_height}, diagonal: {pose.diagonal:.0f}px")
        print(f"Detection confidence: {pose.detection_confidence:.1%}")
        angles = compute_joint_angles(pose)
        print("\nJoint angles:")
        for joint, angle in angles.items():
            print(f"  {joint}: {angle:.1f}°")
        return

    # Handle compare (default)
    if not args.original or not args.inpainted:
        parser.error("--original and --inpainted are required for comparison")

    if not args.json:
        print("Detecting poses (DWPose)...")
    original = detect_pose(args.original)
    inpainted = detect_pose(args.inpainted)

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
        print(f"Original: {len(original.landmarks)} body + {len(original.hand_left_landmarks)} L-hand + "
              f"{len(original.hand_right_landmarks)} R-hand + {len(original.face_landmarks)} face")
        print(f"Inpainted: {len(inpainted.landmarks)} body + {len(inpainted.hand_left_landmarks)} L-hand + "
              f"{len(inpainted.hand_right_landmarks)} R-hand + {len(inpainted.face_landmarks)} face")

    comparison = compare_poses(
        original, inpainted,
        head_threshold_pct=args.head_threshold,
        torso_threshold_pct=args.torso_threshold,
        limbs_threshold_pct=args.limbs_threshold,
        hands_threshold_pct=args.hands_threshold,
        strict=args.strict,
        strict_threshold_pct=args.strict_threshold,
    )

    angle_diffs = compare_angles(original, inpainted)

    if args.json:
        output = comparison.to_dict()
        output["strict_mode"] = args.strict
        output["joint_angles"] = {
            k: {kk: (bool(vv) if kk == "changed" else round(float(vv), 1))
                for kk, vv in v.items()}
            for k, v in angle_diffs.items()
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"POSE COMPARISON RESULT (DWPose — 130 keypoints)")
        print(f"{'='*60}")
        if args.strict:
            print(f"Mode: STRICT (zero tolerance)")
        print(f"Status: {'POSE CHANGED' if comparison.pose_changed else 'POSE SAME'}")
        print(f"Confidence: {comparison.confidence:.1%}")
        print(f"Summary: {comparison.summary}")

        if args.verbose:
            print(f"\n--- Per-Landmark Differences (top 20) ---")
            print(f"{'Landmark':<20} {'Dist (px)':>10} {'Dist (%)':>10} {'Group':>14}")
            print(f"{'-'*56}")
            for d in sorted(comparison.diffs, key=lambda x: x.distance_normalized, reverse=True)[:20]:
                marker = " *" if d.distance_normalized > (args.strict_threshold if args.strict else 3.0) else ""
                print(f"{d.name:<20} {d.distance:>10.1f} {d.distance_normalized:>9.2f}% {d.group:>14}{marker}")

            print(f"\n--- Joint Angle Differences ---")
            for joint, info in angle_diffs.items():
                marker = " *" if info["changed"] else ""
                print(f"{joint:<20} {info['original_deg']:>6.1f}° -> {info['inpainted_deg']:>6.1f}° (D {info['diff_deg']:.1f}°){marker}")

    if args.visualize:
        output_path = args.output or "pose_comparison.png"
        draw_comparison(args.original, args.inpainted, comparison, output_path)
        if not args.json:
            print(f"\nVisualization saved to: {output_path}")

    sys.exit(1 if comparison.pose_changed else 0)


if __name__ == "__main__":
    main()
