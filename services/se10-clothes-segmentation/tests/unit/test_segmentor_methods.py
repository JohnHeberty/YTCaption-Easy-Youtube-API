"""Unit tests for SE10 ClothesSegmentor sub-methods (Phase 2 refactoring).

Tests the extracted methods: _empty_result, _detect, _filter_detections,
_annotate, _build_objects — without loading actual ML models.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest
import supervision as sv

from app.core.constants import CLOTHING_CLASSES
from app.services.segmentor import ClothesSegmentor


@pytest.fixture
def segmentor():
    """Create a ClothesSegmentor with mocked settings (no model loading)."""
    settings = MagicMock()
    settings.device = "cpu"
    settings.box_threshold = 0.10
    settings.text_threshold = 0.10
    settings.max_area_pct = 0.29
    settings.max_objects = 50
    settings.pose_min_confidence = 0.5
    settings.idle_timeout = 300
    with patch.object(ClothesSegmentor, '_load_models'):
        seg = ClothesSegmentor.__new__(ClothesSegmentor)
        seg.settings = settings
        seg._device = "cpu"
        seg._yolo_detector = MagicMock()
        seg._segformer_detector = MagicMock()
        seg._ensemble_detector = MagicMock()
        seg._pose_renderer = None
        seg._idle_timeout = 300
        seg._last_used = 0.0
    return seg


# ─── _empty_result ──────────────────────────────────────────────────────────

class TestEmptyResult:

    def test_returns_correct_structure(self, segmentor):
        import time
        t0 = time.time()
        result = segmentor._empty_result(t0)
        assert result["detected"] is False
        assert result["objects"] == []
        assert result["mask_image"] is None
        assert "processing_time_ms" in result
        assert isinstance(result["processing_time_ms"], float)

    def test_processing_time_is_positive(self, segmentor):
        import time
        t0 = time.time() - 0.1  # 100ms ago
        result = segmentor._empty_result(t0)
        assert result["processing_time_ms"] >= 90.0  # at least ~90ms


# ─── _detect ────────────────────────────────────────────────────────────────

class TestDetect:

    def test_segformer_calls_segment_to_sv_detections(self, segmentor):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        expected_detections = sv.Detections(
            xyxy=np.array([[10, 10, 50, 50]]),
            confidence=np.array([0.9]),
            class_id=np.array([4]),
        )
        segmentor._segformer_detector.segment_to_sv_detections.return_value = expected_detections

        detections, has_masks = segmentor._detect(img, "segformer", "clothes", ["shirt"], 0.1, 0.1)
        assert detections is not None
        assert len(detections) == 1
        segmentor._segformer_detector.segment_to_sv_detections.assert_called_once()

    def test_yolo11_calls_predict(self, segmentor):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        expected_detections = sv.Detections(
            xyxy=np.array([[10, 10, 50, 50]]),
            confidence=np.array([0.9]),
            class_id=np.array([0]),
        )
        segmentor._yolo_detector.predict.return_value = expected_detections

        detections, has_masks = segmentor._detect(img, "yolo11", "person", ["person"], 0.25, 0.1)
        assert detections is not None
        segmentor._yolo_detector.predict.assert_called_once()

    def test_yolo11_empty_returns_none(self, segmentor):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        segmentor._yolo_detector.predict.return_value = sv.Detections.empty()

        detections, has_masks = segmentor._detect(img, "yolo11", "person", ["person"], 0.25, 0.1)
        assert detections is None

    def test_ensemble_calls_detect_ensemble(self, segmentor):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        segmentor._ensemble_detector.detect_ensemble.return_value = {
            "detections": sv.Detections(
                xyxy=np.array([[10, 10, 50, 50]]),
                confidence=np.array([0.9]),
                class_id=np.array([4]),
            ),
            "method": "segformer",
            "coverage_pct": 16.0,
            "detector_results": {},
        }

        detections, has_masks = segmentor._detect(img, "ensemble", "clothes", ["shirt"], 0.1, 0.1)
        assert detections is not None
        segmentor._ensemble_detector.detect_ensemble.assert_called_once()

    def test_ensemble_empty_returns_none(self, segmentor):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        segmentor._ensemble_detector.detect_ensemble.return_value = {
            "detections": None,
            "method": "none",
            "coverage_pct": 0.0,
            "detector_results": {},
        }

        detections, has_masks = segmentor._detect(img, "ensemble", "clothes", ["shirt"], 0.1, 0.1)
        assert detections is None


# ─── _filter_detections ─────────────────────────────────────────────────────

class TestFilterDetections:

    def test_area_filtering(self, segmentor):
        # Create detections where one is too large
        detections = sv.Detections(
            xyxy=np.array([
                [0, 0, 10, 10],    # small (1% of 100x100)
                [0, 0, 90, 90],    # large (81% of 100x100)
            ]),
            confidence=np.array([0.9, 0.8]),
            class_id=np.array([4, 5]),
        )
        # max_area_pct = 0.29 → the large one should be filtered
        result = segmentor._filter_detections(detections, "segformer", 0.29, 10000, 50, False)
        assert len(result) == 1
        assert result.class_id[0] == 4  # only the small one survives

    def test_max_objects_cap(self, segmentor):
        # Create 5 detections, cap to 3
        detections = sv.Detections(
            xyxy=np.array([[i*10, 0, i*10+5, 5] for i in range(5)]),
            confidence=np.array([0.9, 0.8, 0.7, 0.6, 0.5]),
            class_id=np.array([4, 5, 6, 7, 4]),
        )
        result = segmentor._filter_detections(detections, "segformer", 0.80, 10000, 3, False)
        assert len(result) == 3
        # Should keep top 3 by confidence
        assert list(result.confidence) == [0.9, 0.8, 0.7]

    def test_segformer_skips_nesting(self, segmentor):
        # SegFormer should skip nesting filter — each class is independent
        mask1 = np.zeros((100, 100), dtype=bool)
        mask1[10:50, 10:50] = True
        mask2 = np.zeros((100, 100), dtype=bool)
        mask2[20:40, 20:40] = True  # inside mask1

        detections = sv.Detections(
            xyxy=np.array([[10, 10, 50, 50], [20, 20, 40, 40]]),
            confidence=np.array([0.9, 0.8]),
            class_id=np.array([4, 5]),
            mask=np.array([mask1, mask2]),
        )
        result = segmentor._filter_detections(detections, "segformer", 0.80, 10000, 50, True)
        # Both should survive (no nesting filter for SegFormer)
        assert len(result) == 2

    def test_empty_detections(self, segmentor):
        detections = sv.Detections.empty()
        result = segmentor._filter_detections(detections, "segformer", 0.29, 10000, 50, False)
        assert len(result) == 0


# ─── _annotate ──────────────────────────────────────────────────────────────

class TestAnnotate:

    def test_returns_annotated_image(self, segmentor):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        detections = sv.Detections(
            xyxy=np.array([[10, 10, 50, 50]]),
            confidence=np.array([0.9]),
            class_id=np.array([0]),
        )
        result = segmentor._annotate(img, detections, "yolo11", ["person"])
        assert result is not None
        assert result.shape == (100, 100, 3)
        # Should not be all black (annotation was added)
        assert np.any(result > 0)

    def test_segformer_label(self, segmentor):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        detections = sv.Detections(
            xyxy=np.array([[10, 10, 50, 50]]),
            confidence=np.array([0.85]),
            class_id=np.array([4]),  # Upper-clothes
        )
        result = segmentor._annotate(img, detections, "segformer", CLOTHING_CLASSES)
        assert result is not None


# ─── _build_objects ─────────────────────────────────────────────────────────

class TestBuildObjects:

    def test_build_objects_with_masks(self, segmentor):
        mask = np.zeros((100, 100), dtype=bool)
        mask[10:50, 10:50] = True
        detections = sv.Detections(
            xyxy=np.array([[10, 10, 50, 50]]),
            confidence=np.array([0.9]),
            class_id=np.array([4]),
            mask=np.array([mask]),
        )
        objects, masks = segmentor._build_objects(detections, "segformer", CLOTHING_CLASSES, 10000)
        assert len(objects) == 1
        assert objects[0]["class_name"] == "Upper-clothes"
        assert objects[0]["confidence"] == 0.9
        assert len(masks) == 1
        assert masks[0].startswith("data:image/png;base64,")

    def test_build_objects_without_masks(self, segmentor):
        detections = sv.Detections(
            xyxy=np.array([[10, 10, 50, 50]]),
            confidence=np.array([0.9]),
            class_id=np.array([0]),
        )
        objects, masks = segmentor._build_objects(detections, "yolo11", ["person"], 10000)
        assert len(objects) == 1
        assert objects[0]["class_name"] == "person"
        assert len(masks) == 0

    def test_area_pct_calculation(self, segmentor):
        mask = np.zeros((100, 100), dtype=bool)
        mask[0:100, 0:100] = True  # full mask = 10000 pixels
        detections = sv.Detections(
            xyxy=np.array([[0, 0, 100, 100]]),
            confidence=np.array([0.9]),
            class_id=np.array([4]),
            mask=np.array([mask]),
        )
        objects, _ = segmentor._build_objects(detections, "segformer", CLOTHING_CLASSES, 100000)
        # area_pct = area / image_area * 100. area comes from detection.area which is computed from mask
        assert objects[0]["area_pct"] > 0
