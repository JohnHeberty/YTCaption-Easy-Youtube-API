import pytest
from unittest.mock import patch

from app.main import settings as _main_settings


class TestAuthMiddleware:
    def test_no_key_configured_allows_all(self, client):
        with patch.object(_main_settings, "se8_api_key", None):
            resp = client.get("/v1/engines/styles")
        assert resp.status_code == 200

    def test_no_key_returns_401(self, client):
        resp = client.get("/v1/engines/styles")
        assert resp.status_code == 401

    def test_wrong_key_returns_401(self, client):
        resp = client.get("/v1/engines/styles", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_correct_key_allows(self, client, auth_header):
        resp = client.get("/v1/engines/styles", headers=auth_header)
        assert resp.status_code == 200

    def test_health_exempt(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_ping_exempt(self, client):
        resp = client.get("/ping")
        assert resp.status_code == 200

    def test_home_exempt(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_health_deep_exempt(self, client):
        resp = client.get("/health/deep")
        assert resp.status_code == 200

    def test_v1_generation_requires_key(self, client):
        resp = client.post(
            "/v1/generation/text-to-image",
            json={"prompt": "test"},
        )
        assert resp.status_code == 401

    def test_v2_generation_requires_key(self, client):
        resp = client.post(
            "/v2/generation/text-to-image-with-ip",
            json={"prompt": "test"},
        )
        assert resp.status_code == 401

    def test_engines_requires_key(self, client):
        resp = client.get("/v1/engines/styles")
        assert resp.status_code == 401

    def test_tools_requires_key(self, client):
        resp = client.post("/v1/tools/generate_mask", json={"image": ""})
        assert resp.status_code == 401

    def test_files_requires_key(self, client):
        resp = client.get("/files/2026-01-01/test.png")
        assert resp.status_code == 401
