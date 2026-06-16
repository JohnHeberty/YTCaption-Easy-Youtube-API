import pytest
import httpx
import respx


class TestHealthEndpoints:
    @respx.mock
    def test_health_healthy(self, client, mock_fooocus):
        mock_fooocus.get("/ping").mock(return_value=httpx.Response(200, text="pong"))
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["fooocus_api"] == "connected"

    @respx.mock
    def test_health_degraded(self, client, mock_fooocus):
        mock_fooocus.get("/ping").mock(side_effect=httpx.ConnectError("refused"))
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["fooocus_api"] == "disconnected"

    @respx.mock
    def test_health_deep_healthy(self, client, mock_fooocus):
        mock_fooocus.get("/ping").mock(return_value=httpx.Response(200, text="pong"))
        resp = client.get("/health/deep")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "checks" in data

    @respx.mock
    def test_health_deep_degraded(self, client, mock_fooocus):
        mock_fooocus.get("/ping").mock(side_effect=httpx.ConnectError("refused"))
        resp = client.get("/health/deep")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"


class TestPing:
    @respx.mock
    def test_ping_ok(self, client, mock_fooocus):
        mock_fooocus.get("/ping").mock(return_value=httpx.Response(200, text="pong"))
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert resp.json() == "pong"

    @respx.mock
    def test_ping_unavailable(self, client, mock_fooocus):
        mock_fooocus.get("/ping").mock(side_effect=httpx.ConnectError("refused"))
        resp = client.get("/ping")
        assert resp.status_code == 503


class TestHome:
    @respx.mock
    def test_home_returns_html(self, client, mock_fooocus):
        html = "<h2>Fooocus-API</h2><ul><li>test</li></ul>"
        mock_fooocus.get("/").mock(return_value=httpx.Response(200, text=html))
        resp = client.get("/")
        assert resp.status_code == 200
        assert "<h2>" in resp.text
        assert "text/html" in resp.headers.get("content-type", "")

    @respx.mock
    def test_home_fallback_on_error(self, client, mock_fooocus):
        mock_fooocus.get("/").mock(side_effect=httpx.ConnectError("refused"))
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "se8-image-generation"
        assert data["status"] == "ok"

    @respx.mock
    def test_home_json_response(self, client, mock_fooocus):
        mock_fooocus.get("/").mock(return_value=httpx.Response(200, json={"docs": "/docs"}))
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json() == {"docs": "/docs"}
