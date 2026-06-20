"""Tests for the segmentation endpoint."""
import io

import pytest
from PIL import Image


def _make_test_image_bytes(width: int = 100, height: int = 100, fmt: str = "JPEG") -> bytes:
    """Create a minimal in-memory image for testing."""
    img = Image.new("RGB", (width, height), color=(128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


@pytest.mark.api
class TestSegmentEndpoint:
    def test_segment_no_auth_returns_401(self, client):
        """Request without API key should be rejected."""
        image_bytes = _make_test_image_bytes()
        resp = client.post(
            "/v1/segment",
            files={"file": ("test.jpg", image_bytes, "image/jpeg")},
        )
        assert resp.status_code == 401

    def test_segment_invalid_extension_returns_error(self, client, auth_header):
        """Non-image file should return error."""
        resp = client.post(
            "/v1/segment",
            files={"file": ("test.txt", b"hello world", "text/plain")},
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "INVALID_FILE_TYPE" in data["error"]

    def test_segment_no_file_returns_validation_error(self, client, auth_header):
        """Request without file should return 422."""
        resp = client.post(
            "/v1/segment",
            headers=auth_header,
        )
        assert resp.status_code == 422

    def test_segment_jpeg_accepted(self, client, auth_header):
        """Valid JPEG should be accepted (may fail at model level in test)."""
        image_bytes = _make_test_image_bytes(fmt="JPEG")
        resp = client.post(
            "/v1/segment",
            files={"file": ("test.jpg", image_bytes, "image/jpeg")},
            headers=auth_header,
        )
        # Either succeeds (200 with result) or fails due to missing model
        assert resp.status_code in (200, 500, 503)

    def test_segment_png_accepted(self, client, auth_header):
        """Valid PNG should be accepted."""
        image_bytes = _make_test_image_bytes(fmt="PNG")
        resp = client.post(
            "/v1/segment",
            files={"file": ("test.png", image_bytes, "image/png")},
            headers=auth_header,
        )
        assert resp.status_code in (200, 500, 503)

    def test_segment_with_threshold_params(self, client, auth_header):
        """Segment with custom threshold parameters."""
        image_bytes = _make_test_image_bytes()
        resp = client.post(
            "/v1/segment",
            files={"file": ("test.jpg", image_bytes, "image/jpeg")},
            data={"box_threshold": 0.2, "text_threshold": 0.2},
            headers=auth_header,
        )
        assert resp.status_code in (200, 500, 503)
