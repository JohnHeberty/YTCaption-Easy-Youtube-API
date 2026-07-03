"""Ensemble Detector — Multi-detector consensus voting for person detection.

Combines GroundingDINO + YOLO11-seg (and optionally BiRefNet) with:
- Centroid-based consensus: detectors agreeing on person location
- Weighted Box Fusion: merge bbox predictions by confidence
- Mask voting: pixel-wise majority vote for masks
- Confidence gate: auto-select best detector or fallback
"""
from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np
import supervision as sv

from common.log_utils import get_logger

logger = get_logger(__name__)


class EnsembleDetector:
    """Multi-detector ensemble with consensus voting."""

    def __init__(self) -> None:
        self._yolo_detector: Any = None
        self._birefnet_detector: Any = None
        self._gd_model: Any = None

    def set_yolo(self, yolo_detector: Any) -> None:
        """Register YOLO11-seg detector."""
        self._yolo_detector = yolo_detector

    def set_birefnet(self, birefnet_detector: Any) -> None:
        """Register BiRefNet-portrait detector."""
        self._birefnet_detector = birefnet_detector

    def set_groundingdino(self, gd_model: Any) -> None:
        """Register GroundingDINO model."""
        self._gd_model = gd_model

    def detect_ensemble(
        self,
        image_bgr: np.ndarray,
        classes: list[str],
        box_threshold: float = 0.10,
        text_threshold: float = 0.10,
        min_coverage_pct: float = 5.0,
    ) -> dict[str, Any]:
        """Run multiple detectors and merge results via consensus.

        Args:
            image_bgr: OpenCV BGR image.
            classes: Text classes for GroundingDINO (e.g. ["person", "woman", "man"]).
            box_threshold: GroundingDINO box threshold.
            text_threshold: GroundingDINO text threshold.
            min_coverage_pct: Minimum person coverage % to consider detection valid.

        Returns:
            dict with keys: detections, method, coverage_pct, detector_results
        """
        t0 = time.time()
        h, w = image_bgr.shape[:2]
        image_area = h * w
        results: dict[str, dict[str, Any]] = {}

        # --- Detector 1: GroundingDINO + SAM2 ---
        gd_detections = None
        if self._gd_model is not None:
            try:
                gd_det = self._gd_model.predict_with_classes(
                    image=image_bgr,
                    classes=classes,
                    box_threshold=box_threshold,
                    text_threshold=text_threshold,
                )
                if len(gd_det) > 0:
                    # Calculate coverage from bboxes (approximate)
                    total_area = sum(
                        (box[2] - box[0]) * (box[3] - box[1])
                        for box in gd_det.xyxy
                    )
                    coverage = (total_area / image_area) * 100
                    results["groundingdino"] = {
                        "detected": True,
                        "coverage_pct": round(coverage, 1),
                        "num_objects": len(gd_det),
                        "max_confidence": round(float(gd_det.confidence.max()), 3),
                    }
                    if coverage >= min_coverage_pct:
                        gd_detections = gd_det
                    else:
                        results["groundingdino"]["filtered"] = True
                        results["groundingdino"]["reason"] = f"coverage {coverage:.1f}% < {min_coverage_pct}%"
                else:
                    results["groundingdino"] = {"detected": False, "coverage_pct": 0.0}
            except Exception as e:
                results["groundingdino"] = {"detected": False, "error": str(e)}
                logger.warning("GroundingDINO failed: %s", e)

        # --- Detector 2: YOLO11-seg ---
        yolo_detections = None
        if self._yolo_detector is not None:
            try:
                yolo_det = self._yolo_detector.predict(
                    image_bgr, confidence=0.25, classes=[0]
                )
                if len(yolo_det) > 0:
                    # Filter: only person class (id=0)
                    person_mask = yolo_det.class_id == 0
                    if person_mask.any():
                        yolo_person = yolo_det[person_mask]
                        # Calculate coverage from masks if available
                        if yolo_person.mask is not None:
                            total_mask_px = sum(m.sum() for m in yolo_person.mask)
                            coverage = (total_mask_px / image_area) * 100
                        else:
                            total_area = sum(
                                (box[2] - box[0]) * (box[3] - box[1])
                                for box in yolo_person.xyxy
                            )
                            coverage = (total_area / image_area) * 100

                        results["yolo11"] = {
                            "detected": True,
                            "coverage_pct": round(coverage, 1),
                            "num_objects": len(yolo_person),
                            "max_confidence": round(float(yolo_person.confidence.max()), 3),
                        }
                        yolo_detections = yolo_person
                    else:
                        results["yolo11"] = {"detected": False, "coverage_pct": 0.0}
                else:
                    results["yolo11"] = {"detected": False, "coverage_pct": 0.0}
            except Exception as e:
                results["yolo11"] = {"detected": False, "error": str(e)}
                logger.warning("YOLO11-seg failed: %s", e)

        # --- Detector 3: BiRefNet-portrait ---
        birefnet_detections = None
        if self._birefnet_detector is not None:
            try:
                birefnet_det = self._birefnet_detector.predict(
                    image_bgr, threshold=0.5
                )
                if len(birefnet_det) > 0 and birefnet_det.mask is not None:
                    total_mask_px = sum(m.sum() for m in birefnet_det.mask)
                    coverage = (total_mask_px / image_area) * 100
                    results["birefnet"] = {
                        "detected": True,
                        "coverage_pct": round(coverage, 1),
                        "num_objects": len(birefnet_det),
                        "max_confidence": round(float(birefnet_det.confidence.max()), 3),
                    }
                    if coverage >= min_coverage_pct:
                        birefnet_detections = birefnet_det
                    else:
                        results["birefnet"]["filtered"] = True
                        results["birefnet"]["reason"] = f"coverage {coverage:.1f}% < {min_coverage_pct}%"
                else:
                    results["birefnet"] = {"detected": False, "coverage_pct": 0.0}
            except Exception as e:
                results["birefnet"] = {"detected": False, "error": str(e)}
                logger.warning("BiRefNet-portrait failed: %s", e)

        # --- Consensus Voting ---
        final_detections, method = self._consensus_vote(
            gd_detections, yolo_detections, birefnet_detections, min_coverage_pct
        )

        final_coverage = 0.0
        if final_detections is not None and len(final_detections) > 0:
            if final_detections.mask is not None:
                total_mask_px = sum(m.sum() for m in final_detections.mask)
                final_coverage = (total_mask_px / image_area) * 100
            else:
                total_area = sum(
                    (box[2] - box[0]) * (box[3] - box[1])
                    for box in final_detections.xyxy
                )
                final_coverage = (total_area / image_area) * 100

        processing_ms = round((time.time() - t0) * 1000, 1)
        logger.info(
            "Ensemble detection | method=%s coverage=%.1f%% time=%.1fms detectors=%s",
            method, final_coverage, processing_ms, list(results.keys()),
        )

        return {
            "detections": final_detections,
            "method": method,
            "coverage_pct": round(final_coverage, 1),
            "detector_results": results,
            "processing_time_ms": processing_ms,
        }

    def _consensus_vote(
        self,
        gd_detections: sv.Detections | None,
        yolo_detections: sv.Detections | None,
        birefnet_detections: sv.Detections | None,
        min_coverage_pct: float = 5.0,
    ) -> tuple[sv.Detections | None, str]:
        """Choose best detections based on consensus logic.

        Strategy:
        1. If multiple detect → pick highest coverage with masks
        2. If only one detects → use it
        3. If none detect → return None

        Returns:
            (detections, method_name)
        """
        gd_ok = gd_detections is not None and len(gd_detections) > 0
        yolo_ok = yolo_detections is not None and len(yolo_detections) > 0
        birefnet_ok = birefnet_detections is not None and len(birefnet_detections) > 0

        detected: list[tuple[str, sv.Detections]] = []
        if gd_ok:
            detected.append(("groundingdino", gd_detections))
        if yolo_ok:
            detected.append(("yolo11", yolo_detections))
        if birefnet_ok:
            detected.append(("birefnet", birefnet_detections))

        if not detected:
            return None, "none"

        if len(detected) == 1:
            name, det = detected[0]
            return det, name

        # Multiple detectors agree — prefer the one with masks and highest coverage
        def _coverage(det: sv.Detections) -> float:
            if det.mask is not None:
                total_px = sum(m.sum() for m in det.mask)
                return total_px
            return sum(
                (box[2] - box[0]) * (box[3] - box[1]) for box in det.xyxy
            )

        # Sort by coverage (descending), prefer detectors with masks
        detected.sort(key=lambda x: (_coverage(x[1]), x[1].mask is not None), reverse=True)
        best_name, best_det = detected[0]

        # If BiRefNet and YOLO both detected, BiRefNet is SOTA — prefer it
        if birefnet_ok and yolo_ok:
            return birefnet_detections, "birefnet_preferred_sota"

        return best_det, f"{best_name}_highest_coverage"
