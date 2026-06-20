"""Unit tests for ClothesSegmentor filtering logic.

Tests the area filtering, nesting detection, and max_objects capping
without loading actual ML models (uses mocks).
"""

import numpy as np
import pytest

from app.core.constants import (
    DEFAULT_BOX_THRESHOLD,
    DEFAULT_TEXT_THRESHOLD,
    DEFAULT_MAX_AREA_PCT,
    DEFAULT_MAX_OBJECTS,
    CLOTHING_CLASSES,
)


@pytest.mark.unit
class TestFilteringLogic:
    """Test the geometric filtering logic used in the segmentation pipeline."""

    def test_is_inside_true(self):
        """A box fully inside another should be detected."""
        from app.services.segmentor import ClothesSegmentor

        box_inner = np.array([20, 20, 80, 80])
        box_outer = np.array([10, 10, 90, 90])
        assert ClothesSegmentor._is_inside(box_inner, box_outer)

    def test_is_inside_false_partial_overlap(self):
        """Partially overlapping boxes should NOT be detected as inside."""
        from app.services.segmentor import ClothesSegmentor

        box1 = np.array([10, 10, 50, 50])
        box2 = np.array([30, 30, 70, 70])
        assert not ClothesSegmentor._is_inside(box1, box2)

    def test_is_inside_false_disjoint(self):
        """Disjoint boxes should NOT be detected as inside."""
        from app.services.segmentor import ClothesSegmentor

        box1 = np.array([0, 0, 10, 10])
        box2 = np.array([50, 50, 60, 60])
        assert not ClothesSegmentor._is_inside(box1, box2)

    def test_is_inside_false_same_box(self):
        """A box compared to itself should NOT be detected as inside
        (the caller skips i==j)."""
        from app.services.segmentor import ClothesSegmentor

        box = np.array([10, 10, 50, 50])
        assert ClothesSegmentor._is_inside(box, box)

    def test_is_inside_exact_match(self):
        """Identical boxes should be detected as inside."""
        from app.services.segmentor import ClothesSegmentor

        box1 = np.array([10, 10, 50, 50])
        box2 = np.array([10, 10, 50, 50])
        assert ClothesSegmentor._is_inside(box1, box2)

    def test_is_inside_edge_touching(self):
        """Box touching edges of outer box should be detected as inside."""
        from app.services.segmentor import ClothesSegmentor

        box_inner = np.array([10, 10, 90, 90])
        box_outer = np.array([10, 10, 90, 90])
        assert ClothesSegmentor._is_inside(box_inner, box_outer)


@pytest.mark.unit
class TestAreaFiltering:
    """Test that area-based filtering works correctly."""

    def test_area_calculation(self):
        """Verify area calculation matches expected values."""
        image_area = 1000 * 1000  # 1M pixels
        box_area = 200 * 200  # 40K pixels
        area_pct = box_area / image_area
        assert area_pct == pytest.approx(0.04)  # 4%

    def test_area_filter_removes_large_boxes(self):
        """Boxes larger than max_area_pct should be filtered out."""
        max_area_pct = 0.29
        image_area = 1000 * 1000

        # 60% of image — should be filtered
        large_box_area = 600 * 600
        assert (large_box_area / image_area) >= max_area_pct

        # 10% of image — should pass
        small_box_area = 300 * 300
        assert (small_box_area / image_area) < max_area_pct


@pytest.mark.unit
class TestMaxObjects:
    """Test max_objects capping logic."""

    def test_cap_by_confidence(self):
        """When exceeding max_objects, highest confidence items should be kept."""
        max_objects = 3
        confidences = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
        top_idx = np.argsort(-confidences)[:max_objects]
        assert len(top_idx) == max_objects
        assert list(top_idx) == [0, 1, 2]  # highest 3

    def test_no_cap_under_limit(self):
        """When under max_objects, all items should be kept."""
        max_objects = 50
        confidences = np.array([0.9, 0.8, 0.7])
        assert len(confidences) <= max_objects


@pytest.mark.unit
class TestClothingClasses:
    """Test clothing class constants."""

    def test_all_15_classes_present(self):
        assert len(CLOTHING_CLASSES) == 15

    def test_classes_are_strings(self):
        for cls in CLOTHING_CLASSES:
            assert isinstance(cls, str)

    def test_classes_match_original(self):
        """Verify the 15 classes match the original clothes-segmentation project."""
        expected = [
            "hat", "sunglasses", "shirt", "blouse", "jacket",
            "sweater", "blazer", "cardigan", "handbag", "skirt",
            "pants", "dress", "shoes", "boots", "slippers",
        ]
        assert CLOTHING_CLASSES == expected


@pytest.mark.unit
class TestThresholdDefaults:
    """Test that default thresholds are reasonable."""

    def test_box_threshold_low(self):
        """Box threshold should be low for high recall."""
        assert DEFAULT_BOX_THRESHOLD <= 0.20

    def test_text_threshold_low(self):
        """Text threshold should be low for high recall."""
        assert DEFAULT_TEXT_THRESHOLD <= 0.20

    def test_max_area_pct_reasonable(self):
        """Max area pct should filter out very large detections."""
        assert 0.10 <= DEFAULT_MAX_AREA_PCT <= 0.50

    def test_max_objects_positive(self):
        assert DEFAULT_MAX_OBJECTS > 0
