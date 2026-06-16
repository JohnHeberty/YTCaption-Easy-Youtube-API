import pytest
import httpx
import respx


class TestV2Routes:
    @respx.mock
    def test_text_to_image_with_ip(self, client, mock_fooocus, auth_header):
        route = mock_fooocus.post("/v2/generation/text-to-image-with-ip").mock(
            return_value=httpx.Response(200, json=[{"url": "http://img.png"}])
        )
        resp = client.post(
            "/v2/generation/text-to-image-with-ip",
            headers=auth_header,
            json={"prompt": "test", "image_prompts": []},
        )
        assert resp.status_code == 200
        assert route.called

    @respx.mock
    def test_image_upscale_vary_v2(self, client, mock_fooocus, auth_header):
        route = mock_fooocus.post("/v2/generation/image-upscale-vary").mock(
            return_value=httpx.Response(200, json=[{"url": "http://upscaled.png"}])
        )
        resp = client.post(
            "/v2/generation/image-upscale-vary",
            headers=auth_header,
            json={"input_image": "base64data"},
        )
        assert resp.status_code == 200

    @respx.mock
    def test_image_inpaint_outpaint_v2(self, client, mock_fooocus, auth_header):
        route = mock_fooocus.post("/v2/generation/image-inpaint-outpaint").mock(
            return_value=httpx.Response(200, json=[{"url": "http://inpainted.png"}])
        )
        resp = client.post(
            "/v2/generation/image-inpaint-outpaint",
            headers=auth_header,
            json={"input_image": "base64data"},
        )
        assert resp.status_code == 200

    @respx.mock
    def test_image_prompt_v2(self, client, mock_fooocus, auth_header):
        route = mock_fooocus.post("/v2/generation/image-prompt").mock(
            return_value=httpx.Response(200, json=[{"url": "http://prompt.png"}])
        )
        resp = client.post(
            "/v2/generation/image-prompt",
            headers=auth_header,
            json={"prompt": "test"},
        )
        assert resp.status_code == 200

    @respx.mock
    def test_image_enhance_v2(self, client, mock_fooocus, auth_header):
        route = mock_fooocus.post("/v2/generation/image-enhance").mock(
            return_value=httpx.Response(200, json=[{"url": "http://enhanced.png"}])
        )
        resp = client.post(
            "/v2/generation/image-enhance",
            headers=auth_header,
            json={"prompt": "test"},
        )
        assert resp.status_code == 200

    @respx.mock
    def test_v2_preserves_fooocus_status(self, client, mock_fooocus, auth_header):
        mock_fooocus.post("/v2/generation/image-upscale-vary").mock(
            return_value=httpx.Response(500, text="error")
        )
        resp = client.post(
            "/v2/generation/image-upscale-vary",
            headers=auth_header,
            json={"input_image": "x"},
        )
        assert resp.status_code == 500

    @respx.mock
    def test_v2_accept_header(self, client, mock_fooocus, auth_header):
        route = mock_fooocus.post("/v2/generation/image-enhance").mock(
            return_value=httpx.Response(200, json={})
        )
        client.post(
            "/v2/generation/image-enhance?accept=image/webp",
            headers=auth_header,
            json={"prompt": "test"},
        )
        req = route.calls[0].request
        assert req.headers.get("accept") == "image/webp"
