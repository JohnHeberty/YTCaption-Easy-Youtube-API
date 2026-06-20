"""Unit tests for Pydantic domain models."""
import pytest

from app.domain.models import (
    DetectedObject,
    SegmentResult,
    SegmentResponse,
    HealthResponse,
    ErrorResponse,
)
from app.core.constants import ClothingClass, CLOTHING_CLASSES


@pytest.mark.unit
class TestDomainModels:
    def test_detected_object(self):
        obj = DetectedObject(
            class_name="shirt",
            confidence=0.95,
            bbox=[10, 20, 100, 200],
            area_pct=12.5,
        )
        assert obj.class_name == "shirt"
        assert obj.confidence == 0.95
        assert obj.bbox == [10, 20, 100, 200]

    def test_detected_object_confidence_bounds(self):
        with pytest.raises(Exception):
            DetectedObject(
                class_name="hat",
                confidence=1.5,  # out of range
                bbox=[0, 0, 10, 10],
                area_pct=1.0,
            )

    def test_segment_result(self):
        result = SegmentResult(
            detected=True,
            object_count=2,
            objects=[],
            mask_image="data:image/jpeg;base64,abc",
            processing_time_ms=123.4,
        )
        assert result.detected is True
        assert result.object_count == 2

    def test_segment_response_success(self):
        resp = SegmentResponse(
            success=True,
            message="OK",
            result=SegmentResult(
                detected=True,
                object_count=0,
                objects=[],
                processing_time_ms=0,
            ),
        )
        assert resp.success is True
        assert resp.error is None

    def test_segment_response_error(self):
        resp = SegmentResponse(
            success=False,
            message="Failed",
            error="SEGMENTATION_ERROR",
        )
        assert resp.success is False
        assert resp.error == "SEGMENTATION_ERROR"

    def test_health_response(self):
        resp = HealthResponse(
            status="ok",
            model_loaded=True,
            device="cpu",
            version="1.0.0",
        )
        assert resp.status == "ok"

    def test_clothing_classes_enum(self):
        assert len(ClothingClass) == 15
        assert ClothingClass.SHIRT.value == "shirt"
        assert ClothingClass.BOOTS.value == "boots"

    def test_clothing_classes_list(self):
        assert len(CLOTHING_CLASSES) == 15
        assert "hat" in CLOTHING_CLASSES
        assert "shoes" in CLOTHING_CLASSES
