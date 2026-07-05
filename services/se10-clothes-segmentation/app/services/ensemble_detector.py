"""Ensemble Detector — Multi-detector consensus voting for clothing/person detection.

Combines SegFormer B2 + YOLO11-seg with:
- SegFormer B2: pixel-level clothing segmentation (18 classes)
- YOLO11-seg: person detection (class 0)
- Consensus voting: auto-select best detector by mode priority
"""
from __future__ import annotations

import time
from typing import Any

import numpy as np
import supervision as sv

from common.log_utils import get_logger

logger = get_logger(__name__)


class EnsembleDetector:
    """Multi-detector ensemble with consensus voting."""

    def __init__(self) -> None:
        self._yolo_detector: Any = None
        self._segformer_detector: Any = None

    def set_yolo(self, yolo_detector: Any) -> None:
        """Register YOLO11-seg detector."""
        self._yolo_detector = yolo_detector

    def set_segformer(self, segformer_detector: Any) -> None:
        """Register SegFormer B2 detector."""
        self._segformer_detector = segformer_detector

    def detect_ensemble(
        self,
        image_bgr: np.ndarray,
        classes: list[str],
        box_threshold: float = 0.10,
        text_threshold: float = 0.10,
        min_coverage_pct: float = 5.0,
        mode: str = "person",
    ) -> dict[str, Any]:
        """Run multiple detectors and merge results via consensus.

        Args:
            image_bgr: OpenCV BGR image.
            classes: Text classes (used for logging/context, not by detectors directly).
            box_threshold: Unused (kept for API compatibility).
            text_threshold: Unused (kept for API compatibility).
            min_coverage_pct: Minimum coverage % to consider detection valid.
            mode: "person" for person detection, "clothes" for clothing detection.

        Returns:
            dict with keys: detections, method, coverage_pct, detector_results
        """
        t0 = time.time()
        h, w = image_bgr.shape[:2]
        image_area = h * w
        results: dict[str, dict[str, Any]] = {}

        # --- Detector 1: SegFormer B2 (pixel-level clothing segmentation) ---
        segformer_detections = None
        if self._segformer_detector is not None:
            try:
                segformer_result = self._segformer_detector.segment_clothes(image_bgr)
                clothing_mask = segformer_result["clothing_mask"]
                if clothing_mask.any():
                    coverage = segformer_result["total_clothing_pct"]
                    detected = segformer_result["detected_classes"]
                    results["segformer"] = {
                        "detected": True,
                        "coverage_pct": round(coverage, 1),
                        "num_classes": len(detected),
                        "classes": [(cls_id, name, round(area, 1)) for cls_id, name, area in detected],
                    }
                    if coverage >= min_coverage_pct:
                        segformer_detections = self._segformer_detector.segment_to_sv_detections(image_bgr)
                    else:
                        results["segformer"]["filtered"] = True
                        results["segformer"]["reason"] = f"coverage {coverage:.1f}% < {min_coverage_pct}%"
                else:
                    results["segformer"] = {"detected": False, "coverage_pct": 0.0}
            except Exception as e:
                results["segformer"] = {"detected": False, "error": str(e)}
                logger.warning("SegFormer B2 failed: %s", e)

        # --- Detector 2: YOLO11-seg (person detection) ---
        yolo_detections = None
        if self._yolo_detector is not None:
            try:
                yolo_det = self._yolo_detector.predict(
                    image_bgr, confidence=0.25, classes=[0]
                )
                if len(yolo_det) > 0:
                    person_mask = yolo_det.class_id == 0
                    if person_mask.any():
                        yolo_person = yolo_det[person_mask]
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

        # --- Consensus Voting ---
        final_detections, method = self._consensus_vote(
            segformer_detections, yolo_detections,
            min_coverage_pct, mode, image_area,
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
        segformer_detections: sv.Detections | None,
        yolo_detections: sv.Detections | None,
        min_coverage_pct: float = 5.0,
        mode: str = "person",
        image_area: int = 1,
    ) -> tuple[sv.Detections | None, str]:
        """Choose best detections based on consensus logic.

        Strategy:
        - Clothes mode: SegFormer B2 is PRIMARY (pixel-level clothing segmentation)
        - Person mode: YOLO11 > SegFormer
        - Single detector → use it
        - None → return None

        Returns:
            (detections, method_name)
        """
        segformer_ok = segformer_detections is not None and len(segformer_detections) > 0
        yolo_ok = yolo_detections is not None and len(yolo_detections) > 0

        detected: list[tuple[str, sv.Detections]] = []
        if segformer_ok:
            detected.append(("segformer", segformer_detections))
        if yolo_ok:
            detected.append(("yolo11", yolo_detections))

        if not detected:
            return None, "none"

        if len(detected) == 1:
            name, det = detected[0]
            return det, name

        # --- Mode-based priority ---
        if mode == "clothes":
            if segformer_ok:
                return segformer_detections, "segformer_clothes_primary"
            if yolo_ok:
                return yolo_detections, "yolo11_clothes_fallback_person_only"

        # Person mode: YOLO11 > SegFormer
        if yolo_ok:
            return yolo_detections, "yolo11_person_primary"
        if segformer_ok:
            return segformer_detections, "segformer_person_fallback"

        name, det = detected[0]
        return det, f"{name}_first_available"
