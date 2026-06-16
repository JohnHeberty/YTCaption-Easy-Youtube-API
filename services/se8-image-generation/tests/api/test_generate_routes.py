import pytest
import httpx
import respx


class TestV1TextToImage:
    @respx.mock
    def test_raw_proxy_forwards_body(self, client, mock_fooocus, auth_header):
        route = mock_fooocus.post("/v1/generation/text-to-image").mock(
            return_value=httpx.Response(200, json=[{"url": "http://img.png"}])
        )
        resp = client.post(
            "/v1/generation/text-to-image",
            headers={**auth_header, "content-type": "application/json"},
            content=b'{"prompt":"test"}',
        )
        assert resp.status_code == 200
        assert route.called

    @respx.mock
    def test_preserves_fooocus_status(self, client, mock_fooocus, auth_header):
        mock_fooocus.post("/v1/generation/text-to-image").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        resp = client.post(
            "/v1/generation/text-to-image",
            headers={**auth_header, "content-type": "application/json"},
            content=b'{"prompt":"test"}',
        )
        assert resp.status_code == 500

    @respx.mock
    def test_accept_query_param(self, client, mock_fooocus, auth_header):
        route = mock_fooocus.post("/v1/generation/text-to-image").mock(
            return_value=httpx.Response(200, json={})
        )
        client.post(
            "/v1/generation/text-to-image?accept=image/png",
            headers={**auth_header, "content-type": "application/json"},
            content=b'{}',
        )
        req = route.calls[0].request
        assert req.headers.get("accept") == "image/png"


class TestV1ImageRoutes:
    @respx.mock
    def test_image_upscale_vary(self, client, mock_fooocus, auth_header, sample_png):
        route = mock_fooocus.post("/v1/generation/image-upscale-vary").mock(
            return_value=httpx.Response(200, json=[{"url": "http://upscaled.png"}])
        )
        resp = client.post(
            "/v1/generation/image-upscale-vary",
            headers=auth_header,
            files={"input_image": ("test.png", sample_png, "image/png")},
            data={"prompt": "{}"},
        )
        assert resp.status_code == 200

    @respx.mock
    def test_image_inpaint_outpaint(self, client, mock_fooocus, auth_header, sample_png):
        route = mock_fooocus.post("/v1/generation/image-inpaint-outpaint").mock(
            return_value=httpx.Response(200, json=[{"url": "http://inpainted.png"}])
        )
        resp = client.post(
            "/v1/generation/image-inpaint-outpaint",
            headers=auth_header,
            files={"input_image": ("test.png", sample_png, "image/png")},
            data={"prompt": "{}"},
        )
        assert resp.status_code == 200

    @respx.mock
    def test_image_prompt(self, client, mock_fooocus, auth_header, sample_png):
        route = mock_fooocus.post("/v1/generation/image-prompt").mock(
            return_value=httpx.Response(200, json=[{"url": "http://prompt.png"}])
        )
        resp = client.post(
            "/v1/generation/image-prompt",
            headers=auth_header,
            files={"cn_img1": ("test.png", sample_png, "image/png")},
            data={"prompt": "{}"},
        )
        assert resp.status_code == 200

    @respx.mock
    def test_image_enhance(self, client, mock_fooocus, auth_header, sample_png):
        route = mock_fooocus.post("/v1/generation/image-enhance").mock(
            return_value=httpx.Response(200, json=[{"url": "http://enhanced.png"}])
        )
        resp = client.post(
            "/v1/generation/image-enhance",
            headers=auth_header,
            files={"enhance_input_image": ("test.png", sample_png, "image/png")},
            data={"prompt": "{}"},
        )
        assert resp.status_code == 200


class TestV1Stop:
    @respx.mock
    def test_stop(self, client, mock_fooocus, auth_header):
        mock_fooocus.post("/v1/generation/stop").mock(
            return_value=httpx.Response(200, json={"msg": "success"})
        )
        resp = client.post("/v1/generation/stop", headers=auth_header)
        assert resp.status_code == 200


class TestV1QueryRoutes:
    @respx.mock
    def test_query_job(self, client, mock_fooocus, auth_header):
        mock_fooocus.get("/v1/generation/query-job").mock(
            return_value=httpx.Response(200, json={"job_id": "123", "job_status": "SUCCESS"})
        )
        resp = client.get("/v1/generation/query-job?job_id=123", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json()["job_id"] == "123"

    @respx.mock
    def test_query_job_not_found(self, client, mock_fooocus, auth_header):
        mock_fooocus.get("/v1/generation/query-job").mock(
            return_value=httpx.Response(404, text="Job not found")
        )
        resp = client.get("/v1/generation/query-job?job_id=xxx", headers=auth_header)
        assert resp.status_code == 404

    @respx.mock
    def test_job_queue(self, client, mock_fooocus, auth_header):
        mock_fooocus.get("/v1/generation/job-queue").mock(
            return_value=httpx.Response(200, json={"running": 0, "finished": 5})
        )
        resp = client.get("/v1/generation/job-queue", headers=auth_header)
        assert resp.status_code == 200

    @respx.mock
    def test_job_history(self, client, mock_fooocus, auth_header):
        mock_fooocus.get("/v1/generation/job-history").mock(
            return_value=httpx.Response(200, json={"history": []})
        )
        resp = client.get("/v1/generation/job-history", headers=auth_header)
        assert resp.status_code == 200

    @respx.mock
    def test_list_outputs(self, client, mock_fooocus, auth_header):
        mock_fooocus.get("/v1/generation/outputs").mock(
            return_value=httpx.Response(200, json={"days": []})
        )
        resp = client.get("/v1/generation/outputs", headers=auth_header)
        assert resp.status_code == 200
