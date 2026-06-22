"""Unit tests for SE11 Clothes Removal pipeline."""
import base64

import cv2
import numpy as np
import pytest


def _make_test_mask(width: int = 100, height: int = 100, fill_pct: float = 0.5) -> str:
    """Create a test binary mask as base64 data URI."""
    mask = np.zeros((height, width), dtype=np.uint8)
    fill_h = int(height * fill_pct)
    fill_w = int(width * fill_pct)
    mask[:fill_h, :fill_w] = 255
    _, buffer = cv2.imencode(".png", mask)
    b64 = base64.b64encode(buffer).decode("utf-8")
    return f"data:image/png;base64,{b64}"


class TestCombineMasks:
    """Tests for the combine_masks function."""

    def test_combine_single_mask(self):
        from app.services.pipeline import combine_masks

        mask = _make_test_mask(100, 100, 0.5)
        result = combine_masks([mask])

        assert result.startswith("data:image/png;base64,")
        raw = result.split(",", 1)[1]
        decoded = base64.b64decode(raw)
        assert len(decoded) > 0

    def test_combine_two_masks_union(self):
        from app.services.pipeline import combine_masks

        mask1 = _make_test_mask(100, 100, 0.3)
        mask2 = _make_test_mask(100, 100, 0.7)
        result = combine_masks([mask1, mask2])

        assert result.startswith("data:image/png;base64,")
        raw = result.split(",", 1)[1]
        decoded = base64.b64decode(raw)
        nparr = np.frombuffer(decoded, np.uint8)
        combined = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        assert combined is not None
        assert combined.shape == (100, 100)
        # Union should have non-zero pixels
        assert np.any(combined > 0)

    def test_combine_empty_masks_raises(self):
        from app.services.pipeline import combine_masks

        with pytest.raises(ValueError, match="No valid masks"):
            combine_masks([])

    def test_combine_masks_without_data_uri_prefix(self):
        from app.services.pipeline import combine_masks

        # Create raw base64 without data URI prefix
        mask = np.zeros((50, 50), dtype=np.uint8)
        mask[:25, :25] = 255
        _, buffer = cv2.imencode(".png", mask)
        raw_b64 = base64.b64encode(buffer).decode("utf-8")

        result = combine_masks([raw_b64])
        assert result.startswith("data:image/png;base64,")


class TestDecodeImage:
    """Tests for the _decode_image function."""

    def test_decode_base64_with_prefix(self):
        from app.services.pipeline import _decode_image

        img = np.zeros((10, 10, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".jpg", img)
        b64 = base64.b64encode(buffer).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{b64}"

        result = _decode_image(data_uri)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_decode_base64_without_prefix(self):
        from app.services.pipeline import _decode_image

        img = np.zeros((10, 10, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".jpg", img)
        b64 = base64.b64encode(buffer).decode("utf-8")

        result = _decode_image(b64)
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestModels:
    """Tests for Pydantic models."""

    def test_create_request_defaults(self):
        from app.core.models import CreateClothesRemovalRequest

        req = CreateClothesRemovalRequest(image="test_base64")
        assert req.classes is None
        assert req.prompt == ""
        assert req.box_threshold == 0.10
        assert req.inpaint_strength == 1.0

    def test_job_status_transitions(self):
        from app.core.models import ClothesRemovalJob, ClothesRemovalJobStatus, CreateClothesRemovalRequest

        req = CreateClothesRemovalRequest(image="test")
        job = ClothesRemovalJob(job_id="cr_test123", request=req)
        assert job.status == ClothesRemovalJobStatus.QUEUED
        assert job.progress == 0.0

        job.status = ClothesRemovalJobStatus.DETECTING
        job.update_stage("detecting", "processing", progress=50.0)
        assert job.progress > 0.0

        job.update_stage("detecting", "completed")
        job.status = ClothesRemovalJobStatus.INPAINTING
        job.update_stage("inpainting", "processing", progress=50.0)

        job.update_stage("inpainting", "completed")
        job.status = ClothesRemovalJobStatus.COMPLETED
        job.update_progress()
        assert job.progress == 100.0

    def test_job_failure(self):
        from app.core.models import ClothesRemovalJob, ClothesRemovalJobStatus, CreateClothesRemovalRequest

        req = CreateClothesRemovalRequest(image="test")
        job = ClothesRemovalJob(job_id="cr_fail", request=req)
        job.status = ClothesRemovalJobStatus.FAILED
        job.error = "Test error"
        job.update_stage("detecting", "failed", error="Test error")
        assert job.error == "Test error"


class TestConstants:
    """Tests for constants."""

    def test_job_prefix(self):
        from app.core.constants import JOB_ID_PREFIX
        assert JOB_ID_PREFIX == "cr_"

    def test_redis_constants(self):
        from app.core.constants import REDIS_KEY_PREFIX, REDIS_LIST_KEY, REDIS_JOB_TTL
        assert REDIS_KEY_PREFIX == "cr_job:"
        assert REDIS_LIST_KEY == "cr_jobs:list"
        assert REDIS_JOB_TTL == 86400 * 2
