"""Unit tests for SE11 _helpers.py — shared pipeline helpers."""
from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import numpy as np
import pytest

from app.services._helpers import (
    CLOTHES_CLASSES,
    DEFAULT_CLOTHES_NEGATIVE,
    SCORING,
    ScoringWeights,
    combine_masks,
    compute_composite_score,
    decode_image,
    detect_person_with_fallbacks,
    detect_skin_hsv,
    fix_b64_padding,
    restore_face,
    strip_data_uri,
    to_data_uri,
    upscale_result,
)


# ─── ScoringWeights ─────────────────────────────────────────────────────────

class TestScoringWeights:

    def test_default_values(self):
        assert SCORING.skin == 0.40
        assert SCORING.head == 0.20
        assert SCORING.landmark == 0.30
        assert SCORING.clothes == 0.10
        assert SCORING.early_stop == 5.0

    def test_frozen(self):
        with pytest.raises(AttributeError):
            SCORING.skin = 0.50

    def test_custom_values(self):
        custom = ScoringWeights(skin=0.5, head=0.1, landmark=0.2, clothes=0.2, early_stop=3.0)
        assert custom.skin == 0.5
        assert custom.early_stop == 3.0

    def test_weights_sum_to_one(self):
        assert SCORING.skin + SCORING.head + SCORING.landmark + SCORING.clothes == pytest.approx(1.0)


# ─── compute_composite_score ────────────────────────────────────────────────

class TestComputeCompositeScore:

    def test_known_values(self):
        # 0.4*(1-2.0) + 0.2*5.0 + 0.3*8.0 + 0.1*10.0 = -0.4 + 1.0 + 2.4 + 1.0 = 4.0
        score = compute_composite_score(skin_ratio=2.0, head_avg=5.0, clothes_pct=10.0, max_landmark=8.0)
        assert score == 4.0

    def test_perfect_score(self):
        # skin_ratio=10.0 (10x more skin), head=0, clothes=0, landmark=0
        # 0.4*(1-10.0) + 0 + 0 + 0 = -3.6
        score = compute_composite_score(skin_ratio=10.0, head_avg=0.0, clothes_pct=0.0, max_landmark=0.0)
        assert score == -3.6

    def test_worst_score(self):
        # skin_ratio=0 (no skin), head=100, clothes=100, landmark=100
        # 0.4*(1-0) + 0.2*100 + 0.3*100 + 0.1*100 = 0.4 + 20 + 30 + 10 = 60.4
        score = compute_composite_score(skin_ratio=0.0, head_avg=100.0, clothes_pct=100.0, max_landmark=100.0)
        assert score == 60.4

    def test_clamping(self):
        # Values > 100 should be clamped to 100
        score = compute_composite_score(skin_ratio=1.0, head_avg=200.0, clothes_pct=300.0, max_landmark=500.0)
        # 0.4*0 + 0.2*100 + 0.3*100 + 0.1*100 = 60.0
        assert score == 60.0

    def test_returns_float(self):
        result = compute_composite_score(1.0, 0.0, 0.0, 0.0)
        assert isinstance(result, float)

    def test_rounded_to_3_decimals(self):
        result = compute_composite_score(1.333333, 0.0, 0.0, 0.0)
        assert len(str(result).split(".")[-1]) <= 3


# ─── detect_skin_hsv ────────────────────────────────────────────────────────

class TestDetectSkinHsv:

    def test_skin_image(self):
        # Create image with skin-like color in BGR (warm tone)
        # BGR [100, 150, 200] → HSV approx (20°, 127, 200) → within skin range
        img = np.full((100, 100, 3), [100, 150, 200], dtype=np.uint8)
        pct = detect_skin_hsv(img)
        assert pct > 50.0  # Most pixels should be detected as skin

    def test_non_skin_image(self):
        # Create image with blue color (not skin)
        img = np.full((100, 100, 3), [200, 50, 50], dtype=np.uint8)  # BGR blue
        pct = detect_skin_hsv(img)
        assert pct < 10.0  # Very few pixels should be skin

    def test_black_image(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        pct = detect_skin_hsv(img)
        assert pct == 0.0

    def test_returns_float(self):
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        result = detect_skin_hsv(img)
        assert isinstance(result, float)

    def test_range_0_to_100(self):
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        pct = detect_skin_hsv(img)
        assert 0.0 <= pct <= 100.0


# ─── Base64 helpers ─────────────────────────────────────────────────────────

class TestBase64Helpers:

    def test_fix_b64_padding_no_padding_needed(self):
        assert fix_b64_padding("YWJjZA==") == "YWJjZA=="

    def test_fix_b64_padding_missing_one(self):
        assert fix_b64_padding("YWJj") == "YWJj"  # len=4, no missing

    def test_fix_b64_padding_missing_two(self):
        assert fix_b64_padding("YQ") == "YQ=="  # len=2, missing 2

    def test_fix_b64_padding_missing_three(self):
        assert fix_b64_padding("YWI") == "YWI="  # len=3, missing 1

    def test_to_data_uri_already_prefixed(self):
        result = to_data_uri("data:image/png;base64,abc")
        assert result == "data:image/png;base64,abc"

    def test_to_data_uri_adds_prefix(self):
        result = to_data_uri("abc")
        assert result == "data:image/png;base64,abc"

    def test_to_data_uri_custom_mime(self):
        result = to_data_uri("abc", mime="image/jpeg")
        assert result == "data:image/jpeg;base64,abc"

    def test_strip_data_uri_with_prefix(self):
        result = strip_data_uri("data:image/png;base64,abc123")
        assert result == "abc123"

    def test_strip_data_uri_without_prefix(self):
        result = strip_data_uri("abc123")
        assert result == "abc123"

    def test_decode_image_base64(self):
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".jpg", img)
        b64 = base64.b64encode(buf).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{b64}"
        result = decode_image(data_uri)
        assert isinstance(result, bytes)
        assert len(result) > 0


# ─── combine_masks ──────────────────────────────────────────────────────────

class TestCombineMasks:

    def _make_mask(self, w=100, h=100, fill_pct=0.5):
        mask = np.zeros((h, w), dtype=np.uint8)
        fill_h = int(h * fill_pct)
        fill_w = int(w * fill_pct)
        mask[:fill_h, :fill_w] = 255
        _, buf = cv2.imencode(".png", mask)
        return f"data:image/png;base64,{base64.b64encode(buf).decode('utf-8')}"

    def test_single_mask(self):
        result = combine_masks([self._make_mask()], 100, 100)
        assert result is not None
        assert result.shape == (100, 100)

    def test_two_masks_union(self):
        m1 = self._make_mask(100, 100, 0.3)
        m2 = self._make_mask(100, 100, 0.7)
        result = combine_masks([m1, m2], 100, 100)
        assert result is not None
        assert np.any(result > 0)

    def test_empty_masks(self):
        result = combine_masks([], 100, 100)
        assert result is None

    def test_resize_mismatch(self):
        m = self._make_mask(50, 50, 0.5)
        result = combine_masks([m], 100, 100)
        assert result is not None
        assert result.shape == (100, 100)


# ─── Constants ──────────────────────────────────────────────────────────────

class TestConstants:

    def test_clothes_classes_is_string(self):
        assert isinstance(CLOTHES_CLASSES, str)
        assert "shirt" in CLOTHES_CLASSES

    def test_default_clothes_negative_is_string(self):
        assert isinstance(DEFAULT_CLOTHES_NEGATIVE, str)
        assert "clothes" in DEFAULT_CLOTHES_NEGATIVE


# ─── detect_person_with_fallbacks (async, needs mock) ───────────────────────

class TestDetectPersonWithFallbacks:

    @pytest.mark.asyncio
    async def test_no_person_detected(self):
        se10 = AsyncMock()
        se10.segment.return_value = {"detected": False, "masks": []}
        result = await detect_person_with_fallbacks(se10, b"fake", "job1", 100, 100)
        assert result == (None, None, None)

    @pytest.mark.asyncio
    async def test_person_detected_primary(self):
        # Create a real mask
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[10:90, 10:90] = 255  # 80% coverage
        _, buf = cv2.imencode(".png", mask)
        mask_b64 = f"data:image/png;base64,{base64.b64encode(buf).decode('utf-8')}"

        se10 = AsyncMock()
        se10.segment.return_value = {
            "detected": True,
            "masks": [mask_b64],
            "objects": [{"area_pct": 64.0}],
            "controlnet_image": "data:image/png;base64,fake_pose",
        }
        person_binary, person_seg, pose_cn = await detect_person_with_fallbacks(
            se10, b"fake", "job1", 100, 100, include_pose=True,
        )
        assert person_binary is not None
        assert person_seg is not None
        assert pose_cn == "data:image/png;base64,fake_pose"
        assert person_binary.shape == (100, 100)

    @pytest.mark.asyncio
    async def test_no_pose_when_disabled(self):
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[10:90, 10:90] = 255
        _, buf = cv2.imencode(".png", mask)
        mask_b64 = f"data:image/png;base64,{base64.b64encode(buf).decode('utf-8')}"

        se10 = AsyncMock()
        se10.segment.return_value = {
            "detected": True,
            "masks": [mask_b64],
            "objects": [{"area_pct": 64.0}],
        }
        person_binary, person_seg, pose_cn = await detect_person_with_fallbacks(
            se10, b"fake", "job1", 100, 100, include_pose=False,
        )
        assert person_binary is not None
        assert pose_cn is None


# ─── upscale_result (async, needs mock) ─────────────────────────────────────

class TestUpscaleResult:

    @pytest.mark.asyncio
    async def test_upscale_success(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".png", img)
        upscaled_b64 = base64.b64encode(buf.tobytes()).decode("utf-8")

        se8 = AsyncMock()
        se8.upscale.return_value = {"base64": f"data:image/png;base64,{upscaled_b64}"}

        result = await upscale_result(se8, img)
        assert result is not None
        assert result.shape == (100, 100, 3)

    @pytest.mark.asyncio
    async def test_upscale_empty_response(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        se8 = AsyncMock()
        se8.upscale.return_value = {}

        result = await upscale_result(se8, img)
        assert result is None

    @pytest.mark.asyncio
    async def test_upscale_exception(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        se8 = AsyncMock()
        se8.upscale.side_effect = Exception("SE8 down")

        result = await upscale_result(se8, img)
        assert result is None


# ─── restore_face (async, needs mock) ───────────────────────────────────────

class TestRestoreFace:

    @pytest.mark.asyncio
    async def test_restore_success(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".png", img)
        restored_b64 = base64.b64encode(buf.tobytes()).decode("utf-8")

        se8 = AsyncMock()
        se8.restore_face.return_value = {"base64": f"data:image/png;base64,{restored_b64}"}

        result = await restore_face(se8, img)
        assert result is not None

    @pytest.mark.asyncio
    async def test_restore_empty_response(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        se8 = AsyncMock()
        se8.restore_face.return_value = {}

        result = await restore_face(se8, img)
        assert result is None

    @pytest.mark.asyncio
    async def test_restore_exception(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        se8 = AsyncMock()
        se8.restore_face.side_effect = Exception("SE8 down")

        result = await restore_face(se8, img)
        assert result is None
