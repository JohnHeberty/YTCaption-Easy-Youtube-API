import pytest
import httpx
import respx


class TestFileRoutes:
    @respx.mock
    def test_get_output_file_success(self, client, mock_fooocus, auth_header):
        mock_fooocus.get("/files/2026-01-01/test.png").mock(
            return_value=httpx.Response(200, content=b"pngdata", headers={"content-type": "image/png"})
        )
        resp = client.get("/files/2026-01-01/test.png", headers=auth_header)
        assert resp.status_code == 200
        assert resp.content == b"pngdata"
        assert resp.headers["content-type"] == "image/png"

    @respx.mock
    def test_get_output_file_not_found(self, client, mock_fooocus, auth_header):
        mock_fooocus.get("/files/2026-01-01/missing.png").mock(
            return_value=httpx.Response(404, text="not found")
        )
        resp = client.get("/files/2026-01-01/missing.png", headers=auth_header)
        assert resp.status_code == 404

    @respx.mock
    def test_get_output_file_requires_auth(self, client, mock_fooocus):
        mock_fooocus.get("/files/2026-01-01/test.png").mock(
            return_value=httpx.Response(200, content=b"data", headers={"content-type": "image/png"})
        )
        resp = client.get("/files/2026-01-01/test.png")
        assert resp.status_code == 401

    @respx.mock
    def test_get_output_file_preserves_content_type(self, client, mock_fooocus, auth_header):
        mock_fooocus.get("/files/2026-01-01/test.webp").mock(
            return_value=httpx.Response(200, content=b"webpdata", headers={"content-type": "image/webp"})
        )
        resp = client.get("/files/2026-01-01/test.webp", headers=auth_header)
        assert resp.headers["content-type"] == "image/webp"
