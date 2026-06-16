import pytest
import httpx
import respx
from unittest.mock import patch

from app.main import settings as _main_settings


class TestAuthMiddleware:
    @respx.mock
    def test_no_key_configured_allows_all(self, client, mock_fooocus):
        mock_fooocus.get("/v1/engines/all-models").mock(
            return_value=httpx.Response(200, json={})
        )
        with patch.object(_main_settings, "se8_api_key", None):
            resp = client.get("/v1/engines/all-models")
        assert resp.status_code == 200

    @respx.mock
    def test_no_key_returns_401(self, client, mock_fooocus):
        mock_fooocus.get("/v1/engines/all-models").mock(
            return_value=httpx.Response(200, json={})
        )
        resp = client.get("/v1/engines/all-models")
        assert resp.status_code == 401

    @respx.mock
    def test_wrong_key_returns_401(self, client, mock_fooocus):
        mock_fooocus.get("/v1/engines/all-models").mock(
            return_value=httpx.Response(200, json={})
        )
        resp = client.get("/v1/engines/all-models", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    @respx.mock
    def test_correct_key_allows(self, client, mock_fooocus, auth_header):
        mock_fooocus.get("/v1/engines/all-models").mock(
            return_value=httpx.Response(200, json={"models": []})
        )
        resp = client.get("/v1/engines/all-models", headers=auth_header)
        assert resp.status_code == 200

    @respx.mock
    def test_health_exempt(self, client, mock_fooocus):
        mock_fooocus.get("/ping").mock(return_value=httpx.Response(200, text="pong"))
        resp = client.get("/health")
        assert resp.status_code == 200

    @respx.mock
    def test_ping_exempt(self, client, mock_fooocus):
        mock_fooocus.get("/ping").mock(return_value=httpx.Response(200, text="pong"))
        resp = client.get("/ping")
        assert resp.status_code == 200

    @respx.mock
    def test_home_exempt(self, client, mock_fooocus):
        mock_fooocus.get("/").mock(return_value=httpx.Response(200, text="<h2>ok</h2>"))
        resp = client.get("/")
        assert resp.status_code == 200

    @respx.mock
    def test_health_deep_exempt(self, client, mock_fooocus):
        mock_fooocus.get("/ping").mock(return_value=httpx.Response(200, text="pong"))
        resp = client.get("/health/deep")
        assert resp.status_code == 200

    @respx.mock
    def test_v1_generation_requires_key(self, client, mock_fooocus):
        mock_fooocus.post("/v1/generation/stop").mock(
            return_value=httpx.Response(200, json={})
        )
        resp = client.post("/v1/generation/stop")
        assert resp.status_code == 401

    @respx.mock
    def test_v2_generation_requires_key(self, client, mock_fooocus):
        mock_fooocus.post("/v2/generation/image-enhance").mock(
            return_value=httpx.Response(200, json={})
        )
        resp = client.post("/v2/generation/image-enhance", json={})
        assert resp.status_code == 401

    @respx.mock
    def test_engines_requires_key(self, client, mock_fooocus):
        mock_fooocus.get("/v1/engines/styles").mock(
            return_value=httpx.Response(200, json=[])
        )
        resp = client.get("/v1/engines/styles")
        assert resp.status_code == 401

    @respx.mock
    def test_tools_requires_key(self, client, mock_fooocus):
        mock_fooocus.post("/v1/tools/generate_mask").mock(
            return_value=httpx.Response(200, json={})
        )
        resp = client.post("/v1/tools/generate_mask", json={})
        assert resp.status_code == 401

    @respx.mock
    def test_files_requires_key(self, client, mock_fooocus):
        mock_fooocus.get("/files/2026-01-01/test.png").mock(
            return_value=httpx.Response(200, content=b"x", headers={"content-type": "image/png"})
        )
        resp = client.get("/files/2026-01-01/test.png")
        assert resp.status_code == 401
