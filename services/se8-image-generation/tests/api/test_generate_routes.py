import pytest
from unittest.mock import patch, MagicMock
from app.domain.task_models import GenerationFinishReason


class TestV1TextToImage:
    def test_text_to_image_calls_worker(self, client, auth_header):
        mock_result = MagicMock()
        mock_result.im = "2026-01-01/test.png"
        mock_result.seed = "42"
        mock_result.finish_reason = GenerationFinishReason.SUCCESS

        with patch("app.api.generate_routes.call_worker") as mock_call:
            mock_call.return_value = [
                {"base64": None, "url": "/files/2026-01-01/test.png", "seed": "42", "finish_reason": "SUCCESS"}
            ]
            resp = client.post(
                "/v1/generation/text-to-image",
                headers={**auth_header, "content-type": "application/json"},
                json={"prompt": "a cat"},
            )
        assert resp.status_code == 200
        assert mock_call.called

    def test_text_to_image_with_accept_query(self, client, auth_header):
        with patch("app.api.generate_routes.call_worker") as mock_call:
            from fastapi import Response
            mock_call.return_value = Response(content=b"pngbytes", media_type="image/png")
            resp = client.post(
                "/v1/generation/text-to-image?accept=image/png",
                headers={**auth_header, "content-type": "application/json"},
                json={"prompt": "test"},
            )
        assert resp.status_code == 200


class TestV1ImageRoutes:
    def test_image_upscale_vary(self, client, auth_header, sample_png):
        with patch("app.api.generate_routes.call_worker") as mock_call:
            mock_call.return_value = [{"base64": None, "url": "/files/x.png", "seed": "1", "finish_reason": "SUCCESS"}]
            resp = client.post(
                "/v1/generation/image-upscale-vary",
                headers={**auth_header, "content-type": "application/json"},
                json={"prompt": "{}", "input_image": "data:image/png;base64," + sample_png.hex()},
            )
        assert resp.status_code == 200

    def test_image_inpaint_outpaint(self, client, auth_header, sample_png):
        with patch("app.api.generate_routes.call_worker") as mock_call:
            mock_call.return_value = [{"base64": None, "url": "/files/x.png", "seed": "1", "finish_reason": "SUCCESS"}]
            resp = client.post(
                "/v1/generation/image-inpaint-outpaint",
                headers={**auth_header, "content-type": "application/json"},
                json={"prompt": "{}", "input_image": "data:image/png;base64," + sample_png.hex()},
            )
        assert resp.status_code == 200

    def test_image_prompt(self, client, auth_header, sample_png):
        with patch("app.api.generate_routes.call_worker") as mock_call:
            mock_call.return_value = [{"base64": None, "url": "/files/x.png", "seed": "1", "finish_reason": "SUCCESS"}]
            resp = client.post(
                "/v1/generation/image-prompt",
                headers={**auth_header, "content-type": "application/json"},
                json={"prompt": "{}"},
            )
        assert resp.status_code == 200

    def test_image_enhance(self, client, auth_header, sample_png):
        with patch("app.api.generate_routes.call_worker") as mock_call:
            mock_call.return_value = [{"base64": None, "url": "/files/x.png", "seed": "1", "finish_reason": "SUCCESS"}]
            resp = client.post(
                "/v1/generation/image-enhance",
                headers={**auth_header, "content-type": "application/json"},
                json={"prompt": "{}"},
            )
        assert resp.status_code == 200
