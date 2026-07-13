"""Integration tests for SE11 pipeline with diverse image fixtures.

Validates that the pipeline handles different image dimensions, aspect ratios,
and formats without crashing. Does NOT require SE8/SE10 running — uses mocks
for external service calls.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import numpy as np
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# All available test images
TEST_IMAGES = [
    "TESTE1.jpg",
    "TESTE2_small.png",
    "TESTE3_tall.png",
    "TESTE4_landscape.png",
    "TESTE5_large.png",
    "TESTE6_medium.png",
]


def _load_fixture_b64(filename: str) -> tuple[bytes, str]:
    """Load a fixture image and return (raw_bytes, data_uri)."""
    path = FIXTURES_DIR / filename
    raw = path.read_bytes()
    ext = path.suffix.lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    b64 = base64.b64encode(raw).decode("utf-8")
    data_uri = f"data:{mime};base64,{b64}"
    return raw, data_uri


def _make_person_mask(h: int, w: int, coverage: float = 0.6) -> np.ndarray:
    """Create a synthetic person binary mask."""
    mask = np.zeros((h, w), dtype=np.uint8)
    y_start = int(h * (1.0 - coverage))
    mask[y_start:, :] = 255
    return mask


def _make_clothes_mask(h: int, w: int) -> np.ndarray:
    """Create a synthetic clothes binary mask (center torso region)."""
    mask = np.zeros((h, w), dtype=np.uint8)
    y1, y2 = int(h * 0.25), int(h * 0.70)
    x1, x2 = int(w * 0.15), int(w * 0.85)
    mask[y1:y2, x1:x2] = 255
    return mask


class TestImageVariety:
    """Test pipeline components with diverse image fixtures."""

    @pytest.mark.parametrize("filename", TEST_IMAGES)
    def test_decode_image_various_formats(self, filename):
        """Pipeline must decode all fixture images without error."""
        from app.services._helpers import decode_image

        raw, data_uri = _load_fixture_b64(filename)
        result = decode_image(data_uri)
        assert isinstance(result, bytes)
        assert len(result) > 0

        # Verify decoded image is valid
        img = cv2.imdecode(np.frombuffer(result, np.uint8), cv2.IMREAD_COLOR)
        assert img is not None, f"Failed to decode {filename}"
        h, w = img.shape[:2]
        assert h > 0 and w > 0

    @pytest.mark.parametrize("filename", TEST_IMAGES)
    def test_image_dimensions_valid(self, filename):
        """All fixture images must have valid dimensions."""
        raw, data_uri = _load_fixture_b64(filename)
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        assert img is not None
        h, w = img.shape[:2]
        assert 100 <= w <= 8192, f"Width {w} out of range for {filename}"
        assert 100 <= h <= 8192, f"Height {h} out of range for {filename}"

    @pytest.mark.parametrize("filename", TEST_IMAGES)
    def test_combine_masks_various_sizes(self, filename):
        """combine_masks must work with any image dimensions."""
        from app.services._helpers import combine_masks

        raw, data_uri = _load_fixture_b64(filename)
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        h, w = img.shape[:2]

        # Create mask at image dimensions
        mask = _make_person_mask(h, w)
        _, buf = cv2.imencode(".png", mask)
        mask_b64 = f"data:image/png;base64,{base64.b64encode(buf).decode()}"

        result = combine_masks([mask_b64], h, w)
        assert result is not None
        assert result.shape == (h, w)

    @pytest.mark.parametrize("filename", TEST_IMAGES)
    def test_detect_skin_hsv_various_images(self, filename):
        """detect_skin_hsv must handle all image types."""
        from app.services._helpers import detect_skin_hsv

        raw, _ = _load_fixture_b64(filename)
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        assert img is not None

        skin_pct = detect_skin_hsv(img)
        assert isinstance(skin_pct, float)
        assert 0.0 <= skin_pct <= 100.0

    @pytest.mark.parametrize("filename", TEST_IMAGES)
    def test_compute_composite_score_various(self, filename):
        """compute_composite_score must handle all inputs."""
        from app.services._helpers import compute_composite_score

        score = compute_composite_score(
            skin_ratio=1.2, head_avg=0.5, clothes_pct=10.0, max_landmark=2.0
        )
        assert isinstance(score, float)
        assert score >= 0.0

    @pytest.mark.parametrize("filename", TEST_IMAGES)
    def test_to_data_uri_various_formats(self, filename):
        """to_data_uri must handle both JPEG and PNG."""
        from app.services._helpers import to_data_uri

        raw, _ = _load_fixture_b64(filename)
        b64 = base64.b64encode(raw).decode()
        ext = Path(filename).suffix.lower()
        mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

        result = to_data_uri(b64, mime=mime)
        assert result.startswith(f"data:{mime};base64,")


class TestMaskBuildingVariety:
    """Test mask building logic with diverse image dimensions."""

    @pytest.mark.parametrize("filename", TEST_IMAGES)
    def test_head_mask_various_sizes(self, filename):
        """detect_head_mask must work with any image size."""
        from app.services.head_detector import detect_head_mask

        raw, _ = _load_fixture_b64(filename)
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        h, w = img.shape[:2]

        person_mask = _make_person_mask(h, w)
        contours, _ = cv2.findContours(person_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        largest = max(contours, key=cv2.contourArea)
        px, py, pw, ph = cv2.boundingRect(largest)

        head = detect_head_mask(
            orig_img=img, person_binary=person_mask,
            person_bbox=(px, py, pw, ph),
            max_head_pct=0.50, neck_margin_below=0.3,
            dilate_kernel_size=25, dilate_iterations=3,
            expand_up=2.5, expand_w=0.5,
        )
        assert head is not None
        assert head.shape == (h, w)
        assert head.dtype == np.uint8

    @pytest.mark.parametrize("filename", TEST_IMAGES)
    def test_face_oval_mask_various_sizes(self, filename):
        """detect_face_oval_mask must work with any image size."""
        from app.services.head_detector import detect_face_oval_mask

        raw, _ = _load_fixture_b64(filename)
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        h, w = img.shape[:2]

        person_mask = _make_person_mask(h, w)
        face = detect_face_oval_mask(
            orig_img=img, person_binary=person_mask, feather_bottom_px=25
        )
        assert face is not None
        assert face.shape == (h, w)

    @pytest.mark.parametrize("filename", TEST_IMAGES)
    def test_full_mask_pipeline_various(self, filename):
        """Full mask pipeline (person → head → face → inpaint) with various sizes."""
        raw, _ = _load_fixture_b64(filename)
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        h, w = img.shape[:2]

        person = _make_person_mask(h, w)
        clothes = _make_clothes_mask(h, w)

        from app.services.head_detector import detect_head_mask, detect_face_oval_mask

        contours, _ = cv2.findContours(person, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        largest = max(contours, key=cv2.contourArea)
        px, py, pw, ph = cv2.boundingRect(largest)

        head = detect_head_mask(
            orig_img=img, person_binary=person,
            person_bbox=(px, py, pw, ph),
            max_head_pct=0.50, neck_margin_below=0.3,
            dilate_kernel_size=25, dilate_iterations=3,
            expand_up=2.5, expand_w=0.5,
        )
        face = detect_face_oval_mask(
            orig_img=img, person_binary=person, feather_bottom_px=25
        )

        protection = cv2.bitwise_or(head, face)
        inpaint = cv2.bitwise_and(person, cv2.bitwise_not(protection))

        # Apply dilation + ghost face suppression (production pipeline logic)
        dilation_px = max(10, int(min(w, h) * 0.03))
        expand_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation_px, dilation_px))
        inpaint = cv2.dilate(inpaint, expand_kernel, iterations=2)

        person_expanded = cv2.dilate(person, expand_kernel, iterations=3)
        inpaint = cv2.bitwise_and(inpaint, person_expanded)

        # Ghost face suppression
        face_zone = cv2.dilate(protection, expand_kernel, iterations=2)
        ghost_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        near_face = cv2.bitwise_and(inpaint, face_zone)
        near_face = cv2.erode(near_face, ghost_k, iterations=1)
        elsewhere = cv2.bitwise_and(inpaint, cv2.bitwise_not(face_zone))
        inpaint = cv2.bitwise_or(elsewhere, near_face)

        # Closing
        close_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        inpaint = cv2.morphologyEx(inpaint, cv2.MORPH_CLOSE, close_k, iterations=2)

        assert inpaint.shape == (h, w)
        inpaint_pct = (inpaint > 0).sum() / inpaint.size * 100
        assert inpaint_pct > 0, f"No inpaint mask generated for {filename}"
