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

        result = combine_masks([])
        assert result == ""

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


class TestMultiPersonDispatch:
    """Tests for multi-person pipeline dispatch logic."""

    def test_multi_person_pipeline_exists(self):
        from app.services.pipeline_multi_person import MultiPersonPipeline
        assert MultiPersonPipeline is not None

    def test_run_nsfw_dispatches_to_standard_when_single_person(self):
        """run_nsfw should use NSFWProductionPipeline when 1 person detected."""
        from unittest.mock import patch, AsyncMock, MagicMock
        import asyncio
        import cv2
        import numpy as np
        from app.services.pipeline_nsfw import run_nsfw

        mock_person = MagicMock()
        mock_person.area_pct = 25.0

        mock_se10 = AsyncMock()
        mock_se10.close = AsyncMock()

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".png", img)
        img_b64 = "data:image/png;base64," + base64.b64encode(buf).decode()

        with patch(
            "app.services.detection_fallbacks.detect_all_persons",
            new_callable=AsyncMock,
            return_value=([mock_person], None, None),
        ), patch(
            "app.services.pipeline_nsfw.NSFWProductionPipeline"
        ) as MockPipeline, patch(
            "app.infrastructure.http_client.SE10Client",
            return_value=mock_se10,
        ):
            mock_pipeline = AsyncMock()
            MockPipeline.return_value = mock_pipeline

            job = MagicMock()
            job.request.image = img_b64
            job.job_id = "cr_test"
            store = MagicMock()

            asyncio.run(run_nsfw(job, store))

            MockPipeline.assert_called_once()
            mock_pipeline.run.assert_called_once()

    def test_run_nsfw_dispatches_to_multi_when_multiple_persons(self):
        """run_nsfw should use MultiPersonPipeline when >1 person detected."""
        from unittest.mock import patch, AsyncMock, MagicMock
        import asyncio
        import cv2
        import numpy as np
        from app.services.pipeline_nsfw import run_nsfw

        mock_person1 = MagicMock()
        mock_person1.area_pct = 20.0
        mock_person2 = MagicMock()
        mock_person2.area_pct = 18.0

        mock_se10 = AsyncMock()
        mock_se10.close = AsyncMock()

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".png", img)
        img_b64 = "data:image/png;base64," + base64.b64encode(buf).decode()

        with patch(
            "app.services.detection_fallbacks.detect_all_persons",
            new_callable=AsyncMock,
            return_value=([mock_person1, mock_person2], None, None),
        ), patch(
            "app.services.pipeline_multi_person.MultiPersonPipeline"
        ) as MockMulti, patch(
            "app.infrastructure.http_client.SE10Client",
            return_value=mock_se10,
        ):
            mock_multi = AsyncMock()
            MockMulti.return_value = mock_multi

            job = MagicMock()
            job.request.image = img_b64
            job.job_id = "cr_test"
            store = MagicMock()

            asyncio.run(run_nsfw(job, store))

            MockMulti.assert_called_once()
            mock_multi.run.assert_called_once()
