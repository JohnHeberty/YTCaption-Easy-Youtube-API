import pytest
import httpx
import respx
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException

from app.services.image_service import FooocusClient


class TestFooocusClientInit:
    def test_base_url_from_settings(self, fooocus_client):
        assert fooocus_client.base_url == "http://mock-fooocus:8888"

    def test_no_api_key(self):
        with patch("app.services.image_service.settings") as s:
            s.fooocus_api_url = "http://x:8888"
            s.fooocus_api_key = None
            c = FooocusClient()
            assert c.headers == {}

    def test_with_api_key(self):
        with patch("app.services.image_service.settings") as s:
            s.fooocus_api_url = "http://x:8888"
            s.fooocus_api_key = "secret"
            c = FooocusClient()
            assert c.headers == {"X-API-Key": "secret"}

    def test_client_starts_none(self, fooocus_client):
        assert fooocus_client._client is None


class TestBuildHeaders:
    def test_no_accept(self, fooocus_client):
        h = fooocus_client._build_headers()
        assert "Accept" not in h

    def test_with_accept(self, fooocus_client):
        h = fooocus_client._build_headers(accept="image/png")
        assert h["Accept"] == "image/png"

    def test_preserves_base_headers(self):
        with patch("app.services.image_service.settings") as s:
            s.fooocus_api_url = "http://x:8888"
            s.fooocus_api_key = "key123"
            c = FooocusClient()
            h = c._build_headers()
            assert h["X-API-Key"] == "key123"


class TestProxyRequest:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_json_success(self, fooocus_client):
        respx.get("http://mock-fooocus:8888/test").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = await fooocus_client.proxy_request("GET", "/test")
        assert result == {"ok": True}

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_non_json_returns_text(self, fooocus_client):
        respx.get("http://mock-fooocus:8888/test").mock(
            return_value=httpx.Response(200, text="pong")
        )
        result = await fooocus_client.proxy_request("GET", "/test")
        assert result == "pong"

    @respx.mock
    @pytest.mark.asyncio
    async def test_404_raises_http_exception(self, fooocus_client):
        respx.get("http://mock-fooocus:8888/test").mock(
            return_value=httpx.Response(404, text="not found")
        )
        with pytest.raises(HTTPException) as exc_info:
            await fooocus_client.proxy_request("GET", "/test")
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail

    @respx.mock
    @pytest.mark.asyncio
    async def test_500_raises_http_exception(self, fooocus_client):
        respx.post("http://mock-fooocus:8888/test").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        with pytest.raises(HTTPException) as exc_info:
            await fooocus_client.proxy_request("POST", "/test", json_body={})
        assert exc_info.value.status_code == 500

    @respx.mock
    @pytest.mark.asyncio
    async def test_json_body_post(self, fooocus_client):
        route = respx.post("http://mock-fooocus:8888/test").mock(
            return_value=httpx.Response(200, json={"result": "ok"})
        )
        result = await fooocus_client.proxy_request("POST", "/test", json_body={"prompt": "cat"})
        assert result == {"result": "ok"}
        assert route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_params_forwarded(self, fooocus_client):
        route = respx.get("http://mock-fooocus:8888/test").mock(
            return_value=httpx.Response(200, json={})
        )
        await fooocus_client.proxy_request("GET", "/test", params={"a": "1", "b": "2"})
        assert route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_accept_header_forwarded(self, fooocus_client):
        route = respx.post("http://mock-fooocus:8888/test").mock(
            return_value=httpx.Response(200, json={})
        )
        await fooocus_client.proxy_request("POST", "/test", json_body={}, accept="image/png")
        req = route.calls[0].request
        assert req.headers.get("accept") == "image/png"

    @respx.mock
    @pytest.mark.asyncio
    async def test_connection_error_raises_502(self, fooocus_client):
        respx.get("http://mock-fooocus:8888/test").mock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(HTTPException) as exc_info:
            await fooocus_client.proxy_request("GET", "/test")
        assert exc_info.value.status_code == 502


class TestProxyRawPost:
    @respx.mock
    @pytest.mark.asyncio
    async def test_forwards_raw_body(self, fooocus_client):
        route = respx.post("http://mock-fooocus:8888/test").mock(
            return_value=httpx.Response(200, content=b"raw bytes", headers={"content-type": "application/octet-stream"})
        )
        resp = await fooocus_client.proxy_raw_post("/test", b"raw body", "multipart/form-data; boundary=xxx")
        assert resp.status_code == 200
        assert resp.body == b"raw bytes"

    @respx.mock
    @pytest.mark.asyncio
    async def test_preserves_fooocus_status_code(self, fooocus_client):
        respx.post("http://mock-fooocus:8888/test").mock(
            return_value=httpx.Response(422, text="validation error")
        )
        resp = await fooocus_client.proxy_raw_post("/test", b"{}", "application/json")
        assert resp.status_code == 422

    @respx.mock
    @pytest.mark.asyncio
    async def test_accept_header_forwarded(self, fooocus_client):
        route = respx.post("http://mock-fooocus:8888/test").mock(
            return_value=httpx.Response(200, json={})
        )
        await fooocus_client.proxy_raw_post("/test", b"{}", "application/json", accept="image/png")
        req = route.calls[0].request
        assert req.headers.get("accept") == "image/png"


class TestGetOutputFile:
    @respx.mock
    @pytest.mark.asyncio
    async def test_success(self, fooocus_client):
        respx.get("http://mock-fooocus:8888/files/2026-01-01/test.png").mock(
            return_value=httpx.Response(200, content=b"pngdata", headers={"content-type": "image/png"})
        )
        content, ct = await fooocus_client.get_output_file("2026-01-01", "test.png")
        assert content == b"pngdata"
        assert ct == "image/png"

    @respx.mock
    @pytest.mark.asyncio
    async def test_404_raises(self, fooocus_client):
        respx.get("http://mock-fooocus:8888/files/2026-01-01/missing.png").mock(
            return_value=httpx.Response(404, text="not found")
        )
        with pytest.raises(HTTPException) as exc_info:
            await fooocus_client.get_output_file("2026-01-01", "missing.png")
        assert exc_info.value.status_code == 404


class TestHealthCheck:
    @respx.mock
    @pytest.mark.asyncio
    async def test_healthy(self, fooocus_client):
        respx.get("http://mock-fooocus:8888/ping").mock(
            return_value=httpx.Response(200, text="pong")
        )
        assert await fooocus_client.health_check() is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_unhealthy(self, fooocus_client):
        respx.get("http://mock-fooocus:8888/ping").mock(
            return_value=httpx.Response(503, text="down")
        )
        assert await fooocus_client.health_check() is False

    @respx.mock
    @pytest.mark.asyncio
    async def test_connection_error(self, fooocus_client):
        respx.get("http://mock-fooocus:8888/ping").mock(side_effect=httpx.ConnectError("refused"))
        assert await fooocus_client.health_check() is False


class TestClose:
    @pytest.mark.asyncio
    async def test_close_without_client(self, fooocus_client):
        fooocus_client._client = None
        await fooocus_client.close()

    @pytest.mark.asyncio
    async def test_close_with_client(self, fooocus_client):
        fooocus_client._client = httpx.AsyncClient()
        await fooocus_client.close()
        assert fooocus_client._client.is_closed


class TestClientReuse:
    @pytest.mark.asyncio
    async def test_reuses_same_client(self, fooocus_client):
        c1 = await fooocus_client._get_client()
        c2 = await fooocus_client._get_client()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_creates_new_after_close(self, fooocus_client):
        c1 = await fooocus_client._get_client()
        await fooocus_client.close()
        c2 = await fooocus_client._get_client()
        assert c1 is not c2
