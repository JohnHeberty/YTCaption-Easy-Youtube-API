import pytest
from unittest.mock import patch, MagicMock


class TestDescribeImage:
    def test_describe_image_fallback(self, client, auth_header, sample_png):
        with patch.dict("sys.modules", {"modules": None, "modules.util": None}):
            resp = client.post(
                "/v1/tools/describe-image?image_type=Photo",
                headers=auth_header,
                files={"image": ("test.png", sample_png, "image/png")},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "describe" in data


class TestGenerateMask:
    def test_generate_mask_fallback(self, client, auth_header):
        with patch.dict("sys.modules", {"extras": None, "extras.inpaint_mask": None}):
            resp = client.post(
                "/v1/tools/generate_mask",
                headers={**auth_header, "content-type": "application/json"},
                json={"image": "", "mask_model": "u2net"},
            )
        assert resp.status_code == 200
