import pytest
from unittest.mock import patch, MagicMock
from app.api.api_utils import refresh_seed, get_task_type, req_to_params, _decode_image
from app.domain.models import (
    TextToImageRequest,
    ImgUpscaleOrVaryRequest,
    ImgInpaintOrOutpaintRequest,
    ImgPromptRequest,
    ImageEnhanceRequest,
)


class TestRefreshSeed:
    def test_valid_seed(self):
        assert refresh_seed(42) == 42

    def test_negative_seed_random(self):
        seed = refresh_seed(-1)
        assert 0 <= seed <= 2**63 - 1

    def test_invalid_seed_random(self):
        seed = refresh_seed("not_a_number")
        assert 0 <= seed <= 2**63 - 1

    def test_none_seed_random(self):
        seed = refresh_seed(None)
        assert 0 <= seed <= 2**63 - 1


class TestGetTaskType:
    def test_text_to_image(self):
        req = TextToImageRequest(prompt="test")
        assert get_task_type(req).value == "Text to Image"

    def test_upscale_vary(self):
        req = ImgUpscaleOrVaryRequest(prompt="test", uov_method="Disabled")
        assert get_task_type(req).value == "Image Upscale or Variation"

    def test_inpaint_outpaint(self):
        req = ImgInpaintOrOutpaintRequest(prompt="test")
        assert get_task_type(req).value == "Image Inpaint or Outpaint"

    def test_image_prompt(self):
        req = ImgPromptRequest(prompt="test")
        assert get_task_type(req).value == "Image Prompt"

    def test_image_enhance(self):
        req = ImageEnhanceRequest(prompt="test")
        assert get_task_type(req).value == "Image Enhancement"


class TestDecodeImage:
    def test_empty_string(self):
        assert _decode_image("") is None
        assert _decode_image(None) is None

    def test_http_url(self):
        assert _decode_image("http://example.com/img.png") == "http://example.com/img.png"

    def test_https_url(self):
        assert _decode_image("https://example.com/img.png") == "https://example.com/img.png"

    def test_base64_data(self):
        import base64
        data = base64.b64encode(b"hello").decode()
        result = _decode_image(data)
        assert result == b"hello"

    def test_base64_with_prefix(self):
        import base64
        data = base64.b64encode(b"hello").decode()
        result = _decode_image(f"data:image/png;base64,{data}")
        assert result == b"hello"


class TestReqToParams:
    def test_text_to_image_params(self):
        req = TextToImageRequest(
            prompt="sunset",
            negative_prompt="ugly",
            image_seed=42,
            image_number=1,
        )
        params = req_to_params(req)
        assert params["prompt"] == "sunset"
        assert params["negative_prompt"] == "ugly"
        assert params["image_seed"] == 42
        assert params["image_number"] == 1

    def test_upscale_params(self):
        req = ImgUpscaleOrVaryRequest(
            prompt="test",
            uov_method="Upscale (2x)",
        )
        params = req_to_params(req)
        assert params["uov_method"] == "Upscale (2x)"
