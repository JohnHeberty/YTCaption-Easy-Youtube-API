import pytest
from unittest.mock import patch, MagicMock, PropertyMock


class TestHealthEndpoints:
    def test_health_healthy(self, client):
        with patch("app.services.worker.worker_queue") as mock_q:
            mock_q.queue = []
            resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "se9-image-engine"

    def test_health_degraded(self, client):
        mock_q = MagicMock()
        type(mock_q).queue = PropertyMock(side_effect=Exception("boom"))
        with patch("app.services.worker.worker_queue", mock_q):
            resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"

    def test_health_deep_healthy(self, client):
        with patch("app.services.worker.worker_queue") as mock_q:
            mock_q.queue = []
            resp = client.get("/health/deep")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "checks" in data

    def test_health_deep_degraded(self, client):
        mock_q = MagicMock()
        type(mock_q).queue = PropertyMock(side_effect=Exception("boom"))
        with patch("app.services.worker.worker_queue", mock_q):
            resp = client.get("/health/deep")
        assert resp.status_code == 200
        data = resp.json()
        assert "checks" in data


class TestPing:
    def test_ping_ok(self, client):
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert resp.json() == "pong"


class TestHome:
    def test_home_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "SE8 Image Engine" in resp.text

    def test_home_has_docs_links(self, client):
        resp = client.get("/")
        assert "/docs" in resp.text
        assert "/redoc" in resp.text
