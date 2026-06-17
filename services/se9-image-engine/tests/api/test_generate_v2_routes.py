import pytest
from unittest.mock import patch, MagicMock


class TestV2Routes:
    def test_text_to_image_with_ip(self, client, auth_header):
        with patch("app.api.generate_v2_routes.call_worker") as mock_call:
            mock_call.return_value = [{"base64": None, "url": "/files/x.png", "seed": "1", "finish_reason": "SUCCESS"}]
            resp = client.post(
                "/v2/generation/text-to-image-with-ip",
                headers={**auth_header, "content-type": "application/json"},
                json={"prompt": "test", "image_prompts": []},
            )
        assert resp.status_code == 200

    def test_image_upscale_vary_v2(self, client, auth_header):
        with patch("app.api.generate_v2_routes.call_worker") as mock_call:
            mock_call.return_value = [{"base64": None, "url": "/files/x.png", "seed": "1", "finish_reason": "SUCCESS"}]
            resp = client.post(
                "/v2/generation/image-upscale-vary",
                headers={**auth_header, "content-type": "application/json"},
                json={"prompt": "test", "uov_method": "Disabled"},
            )
        assert resp.status_code == 200

    def test_image_inpaint_outpaint_v2(self, client, auth_header):
        with patch("app.api.generate_v2_routes.call_worker") as mock_call:
            mock_call.return_value = [{"base64": None, "url": "/files/x.png", "seed": "1", "finish_reason": "SUCCESS"}]
            resp = client.post(
                "/v2/generation/image-inpaint-outpaint",
                headers={**auth_header, "content-type": "application/json"},
                json={"prompt": "test"},
            )
        assert resp.status_code == 200

    def test_image_prompt_v2(self, client, auth_header):
        with patch("app.api.generate_v2_routes.call_worker") as mock_call:
            mock_call.return_value = [{"base64": None, "url": "/files/x.png", "seed": "1", "finish_reason": "SUCCESS"}]
            resp = client.post(
                "/v2/generation/image-prompt",
                headers={**auth_header, "content-type": "application/json"},
                json={"prompt": "test", "image_prompts": []},
            )
        assert resp.status_code == 200

    def test_image_enhance_v2(self, client, auth_header):
        with patch("app.api.generate_v2_routes.call_worker") as mock_call:
            mock_call.return_value = [{"base64": None, "url": "/files/x.png", "seed": "1", "finish_reason": "SUCCESS"}]
            resp = client.post(
                "/v2/generation/image-enhance",
                headers={**auth_header, "content-type": "application/json"},
                json={"prompt": "test"},
            )
        assert resp.status_code == 200

    def test_v2_pads_image_prompts(self, client, auth_header):
        with patch("app.api.generate_v2_routes.call_worker") as mock_call:
            mock_call.return_value = []
            client.post(
                "/v2/generation/text-to-image-with-ip",
                headers={**auth_header, "content-type": "application/json"},
                json={"prompt": "test", "image_prompts": [{"cn_img": None}]},
            )
        req = mock_call.call_args[0][0]
        assert len(req.image_prompts) == 5
