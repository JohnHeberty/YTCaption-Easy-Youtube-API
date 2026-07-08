"""Pose validation utilities for NSFW pipelines.

Extracted from pipeline_nsfw.py.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

from common.log_utils import get_logger

logger = get_logger(__name__)


async def validate_pose_async(
    original_path: str,
    inpainted_path: str,
    attempt: int = 1,
    max_attempts: int = 3,
    strict: bool = True,
    head_threshold_pct: float = 0.3,
    torso_threshold_pct: float = 0.5,
    limbs_threshold_pct: float = 1.5,
) -> dict:
    """Run pose_validator.py as subprocess and return JSON result.

    Falls back to importing validate_pose directly if the script doesn't exist.
    """
    validator_script = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "validators", "pose_validator.py",
    )
    if not os.path.exists(validator_script):
        sys.path.insert(0, os.path.dirname(validator_script))
        try:
            from validators.pose_validator import validate_pose
            return validate_pose(
                original_path=original_path,
                inpainted_path=inpainted_path,
                attempt=attempt,
                max_attempts=max_attempts,
                strict=strict,
                head_threshold_pct=head_threshold_pct,
                torso_threshold_pct=torso_threshold_pct,
                limbs_threshold_pct=limbs_threshold_pct,
            )
        except ImportError:
            return {"pose_changed": False, "confidence": 0.0, "recommendation": "accept",
                    "details": {"head_pct": 0.0, "torso_pct": 0.0, "limbs_pct": 0.0, "max_landmark_pct": 0.0}}

    cmd = [
        sys.executable, validator_script,
        "--original", original_path,
        "--inpainted", inpainted_path,
        "--attempt", str(attempt),
        "--max-attempts", str(max_attempts),
        "--head-threshold", str(head_threshold_pct),
        "--torso-threshold", str(torso_threshold_pct),
        "--limbs-threshold", str(limbs_threshold_pct),
        "--json",
    ]
    if strict:
        cmd.append("--strict")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode in (0, 1):
            return json.loads(stdout.decode())
        else:
            logger.warning("pose_validator failed (rc=%d): %s", proc.returncode, stderr.decode()[:200])
            return {"pose_changed": False, "confidence": 0.0, "recommendation": "accept",
                    "details": {"head_pct": 0.0, "torso_pct": 0.0, "limbs_pct": 0.0, "max_landmark_pct": 0.0}}
    except Exception as e:
        logger.warning("pose_validator error: %s", e)
        return {"pose_changed": False, "confidence": 0.0, "recommendation": "accept",
                "details": {"head_pct": 0.0, "torso_pct": 0.0, "limbs_pct": 0.0, "max_landmark_pct": 0.0}}
