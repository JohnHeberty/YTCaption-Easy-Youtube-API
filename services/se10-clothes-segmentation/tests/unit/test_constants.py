"""Unit tests for constants."""
import pytest

from app.core.constants import (
    ClothingClass,
    CLOTHING_CLASSES,
    DEFAULT_BOX_THRESHOLD,
    DEFAULT_TEXT_THRESHOLD,
    DEFAULT_MAX_AREA_PCT,
    DEFAULT_MAX_OBJECTS,
    ALLOWED_EXTENSIONS,
)


@pytest.mark.unit
class TestConstants:
    def test_clothing_class_count(self):
        assert len(ClothingClass) == 15

    def test_clothing_classes_list_matches_enum(self):
        assert CLOTHING_CLASSES == [c.value for c in ClothingClass]

    def test_default_thresholds_are_low(self):
        assert DEFAULT_BOX_THRESHOLD == 0.10
        assert DEFAULT_TEXT_THRESHOLD == 0.10

    def test_max_area_pct(self):
        assert 0 < DEFAULT_MAX_AREA_PCT < 1.0

    def test_max_objects_positive(self):
        assert DEFAULT_MAX_OBJECTS > 0

    def test_allowed_extensions(self):
        assert ".jpg" in ALLOWED_EXTENSIONS
        assert ".jpeg" in ALLOWED_EXTENSIONS
        assert ".png" in ALLOWED_EXTENSIONS
        assert ".gif" not in ALLOWED_EXTENSIONS
