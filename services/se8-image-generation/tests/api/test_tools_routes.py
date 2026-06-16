import pytest
import httpx
import respx


class TestDescribeImage:
    @respx.mock
    def test_describe_image_multipart(self, client, mock_fooocus, auth_header, sample_png):
        route = mock_fooocus.post("/v1/tools/describe-image").mock(
            return_value=httpx.Response(200, json={"describe": "a colorful image"})
        )
        resp = client.post(
            "/v1/tools/describe-image",
            headers=auth_header,
            files={"image": ("test.png", sample_png, "image/png")},
        )
        assert resp.status_code == 200
        assert resp.json()["describe"] == "a colorful image"

    @respx.mock
    def test_describe_image_raw_proxy(self, client, mock_fooocus, auth_header, sample_png):
        route = mock_fooocus.post("/v1/tools/describe-image").mock(
            return_value=httpx.Response(200, json={"describe": "test"})
        )
        client.post(
            "/v1/tools/describe-image",
            headers=auth_header,
            files={"image": ("test.png", sample_png, "image/png")},
            data={"image_type": "photo"},
        )
        req = route.calls[0].request
        assert "multipart" in req.headers.get("content-type", "")

    @respx.mock
    def test_describe_image_error(self, client, mock_fooocus, auth_header, sample_png):
        mock_fooocus.post("/v1/tools/describe-image").mock(
            return_value=httpx.Response(500, text="model error")
        )
        resp = client.post(
            "/v1/tools/describe-image",
            headers=auth_header,
            files={"image": ("test.png", sample_png, "image/png")},
        )
        assert resp.status_code == 500


class TestGenerateMask:
    @respx.mock
    def test_generate_mask(self, client, mock_fooocus, auth_header):
        mock_fooocus.post("/v1/tools/generate_mask").mock(
            return_value=httpx.Response(200, json={"mask": "base64data"})
        )
        resp = client.post(
            "/v1/tools/generate_mask",
            headers=auth_header,
            json={"image": "base64", "prompt": "mask area"},
        )
        assert resp.status_code == 200
        assert resp.json()["mask"] == "base64data"

    @respx.mock
    def test_generate_mask_error(self, client, mock_fooocus, auth_header):
        mock_fooocus.post("/v1/tools/generate_mask").mock(
            return_value=httpx.Response(422, text="invalid")
        )
        resp = client.post(
            "/v1/tools/generate_mask",
            headers=auth_header,
            json={"invalid": True},
        )
        assert resp.status_code == 422
