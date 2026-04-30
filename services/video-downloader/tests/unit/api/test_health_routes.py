import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient


@pytest.mark.unit
class TestHealthRoutes:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_metrics_returns_200(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200


@pytest.mark.unit
class TestRootEndpoint:
    def test_root_returns_service_info(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Video Downloader Service"