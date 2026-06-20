"""Tests for health check endpoints."""
import pytest


@pytest.mark.api
class TestHealthEndpoints:
    def test_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "model_loaded" in data
        assert "version" in data

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_deep_returns_200(self, client):
        resp = client.get("/health/deep")
        assert resp.status_code == 200
        data = resp.json()
        assert "checkpoints" in data
        assert "uptime_s" in data

    def test_ping_returns_200(self, client):
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert resp.json()["pong"] is True
