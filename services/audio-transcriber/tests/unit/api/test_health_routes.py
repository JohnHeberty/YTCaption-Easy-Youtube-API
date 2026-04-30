import pytest


@pytest.mark.unit
class TestHealthRoutes:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_languages_returns_200(self, client):
        response = client.get("/languages")
        assert response.status_code == 200

    def test_engines_returns_200(self, client):
        response = client.get("/engines")
        assert response.status_code == 200