"""Pose rendering for ControlNet conditioning.

Generates an OpenPose-style stick figure from an image using MediaPipe Pose.
This output can be used as a control image for OpenPose ControlNet in SE8.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import mediapipe as mp
import numpy as np

mp_pose = mp.solutions.pose


@dataclass
class PoseLandmark:
    """Single body landmark."""
    name: str
    x: float
    y: float
    visibility: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "x": round(float(self.x), 1),
            "y": round(float(self.y), 1),
            "visibility": round(float(self.visibility), 3),
        }


class PoseRenderer:
    """MediaPipe Pose → OpenPose-style stick figure."""

    def __init__(self, min_detection_confidence: float = 0.5) -> None:
        self.min_detection_confidence = min_detection_confidence
        self._pose = mp_pose.Pose(
            static_image_mode=True,
            model_complexity=1,  # full; heavy downloads on demand and needs write perms
            min_detection_confidence=min_detection_confidence,
        )

    def detect(self, rgb_image: np.ndarray) -> list[PoseLandmark] | None:
        """Detect pose landmarks in an RGB image."""
        results = self._pose.process(rgb_image)
        if not results.pose_landmarks:
            return None
        h, w = rgb_image.shape[:2]
        return [
            PoseLandmark(
                name=mp_pose.PoseLandmark(idx).name,
                x=lm.x * w,
                y=lm.y * h,
                visibility=lm.visibility,
            )
            for idx, lm in enumerate(results.pose_landmarks.landmark)
        ]

    def render_stick_figure(
        self,
        landmarks: list[PoseLandmark],
        image_size: tuple[int, int],
        thickness: int = 6,
    ) -> np.ndarray:
        """Render an OpenPose-style stick figure on a black background.

        Args:
            landmarks: List of detected landmarks.
            image_size: (height, width) of output image.
            thickness: Line thickness for limbs.

        Returns:
            BGR numpy image (black background, colored skeleton).
        """
        h, w = image_size
        canvas = np.zeros((h, w, 3), dtype=np.uint8)

        lm_by_name = {lm.name: lm for lm in landmarks}

        def get(name: str) -> PoseLandmark | None:
            lm = lm_by_name.get(name)
            return lm if lm is not None and lm.visibility > 0.5 else None

        def pt(name: str) -> tuple[int, int] | None:
            lm = get(name)
            return None if lm is None else (int(lm.x), int(lm.y))

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

        # Head
        nose = pt("NOSE")
        left_ear = pt("LEFT_EAR")
        right_ear = pt("RIGHT_EAR")
        if nose is not None and left_ear is not None and right_ear is not None:
            head_radius = max(10, int(abs(left_ear[0] - right_ear[0]) * 0.7))
            cv2.circle(canvas, nose, head_radius, c_head, thickness, cv2.LINE_AA)
            circle(nose, c_head, radius=5)
        elif nose is not None:
            circle(nose, c_head, radius=10)

        # Torso
        ls = pt("LEFT_SHOULDER")
        rs = pt("RIGHT_SHOULDER")
        lh = pt("LEFT_HIP")
        rh = pt("RIGHT_HIP")
        line(ls, rs, c_torso)
        line(lh, rh, c_torso)
        line(ls, lh, c_torso)
        line(rs, rh, c_torso)

        # Arms
        le = pt("LEFT_ELBOW")
        lw = pt("LEFT_WRIST")
        line(ls, le, c_arm_l)
        line(le, lw, c_arm_l)

        re = pt("RIGHT_ELBOW")
        rw = pt("RIGHT_WRIST")
        line(rs, re, c_arm_r)
        line(re, rw, c_arm_r)

        # Legs
        lk = pt("LEFT_KNEE")
        la = pt("LEFT_ANKLE")
        line(lh, lk, c_leg_l)
        line(lk, la, c_leg_l)

        rk = pt("RIGHT_KNEE")
        ra = pt("RIGHT_ANKLE")
        line(rh, rk, c_leg_r)
        line(rk, ra, c_leg_r)

        # Joints
        for p in [ls, rs, le, re, lw, rw, lh, rh, lk, rk, la, ra]:
            circle(p, (255, 255, 255), radius=thickness)

        return canvas
