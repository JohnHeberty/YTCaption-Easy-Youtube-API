"""PersonData — per-person data structure for multi-person pipeline support.

Provides a dataclass that holds all per-person detection results (mask, face,
pose, FaceID embedding) and a centroid-based matching utility to associate
results from different detectors (SE10, InsightFace, DWPose) to the correct
person.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import cv2 as _cv2


@dataclass
class PersonData:
    """All detection results for a single person in the image."""
    person_id: int
    binary_mask: np.ndarray              # HxW uint8 (0/255)
    bbox: tuple[int, int, int, int]      # (x, y, w, h)
    centroid: tuple[float, float]        # (cx, cy) — center of mass
    area_pct: float                      # percentage of image area

    # Populated by matching
    face_mask: np.ndarray | None = None
    hair_mask: np.ndarray | None = None
    faceid_embedding: list[list[float]] | None = None
    face_bbox: tuple[int, int, int, int] | None = None  # largest face bbox

    # Pose (per-person)
    pose_landmarks: list[dict[str, Any]] | None = None
    pose_changed: bool = False

    # IP-Adapter reference
    ip_ref_img: np.ndarray | None = None
    ip_ref_b64: str = ""

    # Clothes region (per-person)
    clothes_mask: np.ndarray | None = None


def compute_centroid(binary_mask: np.ndarray) -> tuple[float, float]:
    """Compute center of mass of a binary mask."""
    moments = _cv2.moments(binary_mask)
    if moments["m00"] == 0:
        h, w = binary_mask.shape[:2]
        return (w / 2.0, h / 2.0)
    cx = moments["m10"] / moments["m00"]
    cy = moments["m01"] / moments["m00"]
    return (cx, cy)


def compute_bbox(binary_mask: np.ndarray) -> tuple[int, int, int, int]:
    """Compute bounding box (x, y, w, h) of a binary mask."""
    contours, _ = _cv2.findContours(binary_mask, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        h, w = binary_mask.shape[:2]
        return (0, 0, w, h)
    largest = max(contours, key=_cv2.contourArea)
    return _cv2.boundingRect(largest)


def match_by_centroid(
    persons: list[PersonData],
    detections: list[dict[str, Any]],
    max_distance_px: float = 200.0,
    centroid_key: str = "centroid",
) -> dict[int, int]:
    """Match detections to persons by nearest centroid distance.

    Args:
        persons: List of PersonData with centroids computed.
        detections: List of dicts, each with a 'centroid' key (or key specified
                    by centroid_key) as (cx, cy) tuple.
        max_distance_px: Maximum distance for a match. Detections beyond this
                         distance are unmatched.
        centroid_key: Key in detection dicts that holds the centroid.

    Returns:
        Dict mapping person_id -> detection index. Unmatched persons are absent.
    """
    if not persons or not detections:
        return {}

    # Build distance matrix
    p_centroids = np.array([p.centroid for p in persons])
    d_centroids = np.array([d[centroid_key] for d in detections])

    matched: dict[int, int] = {}
    used_dets: set[int] = set()

    # Greedy nearest-neighbor matching (good enough for small N)
    for pi, person in enumerate(persons):
        best_di = -1
        best_dist = max_distance_px
        for di, det_cent in enumerate(d_centroids):
            if di in used_dets:
                continue
            dist = np.linalg.norm(p_centroids[pi] - det_cent)
            if dist < best_dist:
                best_dist = dist
                best_di = di
        if best_di >= 0:
            matched[person.person_id] = best_di
            used_dets.add(best_di)

    return matched


def create_persons_from_se10(
    person_seg: dict,
    orig_h: int,
    orig_w: int,
    min_area_pct: float = 5.0,
) -> list[PersonData]:
    """Create PersonData list from SE10 segmentation result.

    Instead of picking only the largest person (old behavior), returns ALL
    detected persons above min_area_pct.

    Args:
        person_seg: SE10 segment() response dict with 'objects' and 'masks'.
        orig_h: Original image height.
        orig_w: Original image width.
        min_area_pct: Minimum area percentage to include a person.

    Returns:
        List of PersonData, sorted by area descending.
    """
    if not person_seg.get("detected") or not person_seg.get("masks"):
        return []

    persons: list[PersonData] = []
    for i, obj in enumerate(person_seg.get("objects", [])):
        area_pct = obj.get("area_pct", 0)
        if area_pct < min_area_pct:
            continue

        # Decode mask
        raw = obj.get("mask") or (person_seg["masks"][i] if i < len(person_seg["masks"]) else None)
        if raw is None:
            continue

        from ...shared.image_utils import strip_data_uri, fix_b64_padding
        import base64
        raw_clean = strip_data_uri(raw)
        mask_bytes = base64.b64decode(fix_b64_padding(raw_clean))
        mask = _cv2.imdecode(np.frombuffer(mask_bytes, np.uint8), _cv2.IMREAD_GRAYSCALE)
        if mask is None:
            continue
        if mask.shape[:2] != (orig_h, orig_w):
            mask = _cv2.resize(mask, (orig_w, orig_h))

        binary = (mask > 127).astype(np.uint8) * 255

        # Fill holes
        kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (7, 7))
        binary = _cv2.morphologyEx(binary, _cv2.MORPH_CLOSE, kernel, iterations=3)

        centroid = compute_centroid(binary)
        bbox = compute_bbox(binary)

        persons.append(PersonData(
            person_id=i,
            binary_mask=binary,
            bbox=bbox,
            centroid=centroid,
            area_pct=area_pct,
        ))

    # Sort by area descending (largest first)
    persons.sort(key=lambda p: p.area_pct, reverse=True)

    # Re-assign sequential IDs after sorting
    for idx, p in enumerate(persons):
        p.person_id = idx

    return persons
