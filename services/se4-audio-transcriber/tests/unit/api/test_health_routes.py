import pytest


@pytest.mark.unit
class TestHealthRoutes:
    @pytest.fixture(autouse=True)
    def _mock_health_checkers(self, monkeypatch):
        """Mock all health check functions so they return 'ok' regardless of system state.

        Patch where the functions are USED (health_routes), not where defined."""
        mock_ffmpeg = lambda: {"status": "ok", "message": "FFMPEG available"}
        monkeypatch.setattr("app.api.health_routes.check_ffmpeg", mock_ffmpeg)

        mock_disk = lambda path: {"status": "ok", "free_gb": 10.0, "total_gb": 50.0}
        monkeypatch.setattr(
            "app.api.health_routes.check_disk_space",
            mock_disk
        )

        def mock_whisper(processor, settings):
            return {"status": "ok", "model_loaded": True}

        monkeypatch.setattr(
            "app.api.health_routes.check_whisper_model",
            mock_whisper
        )

    @pytest.fixture(autouse=True)
    def _set_api_key(self, client):
        """Add API key to client headers."""
        client.headers["X-API-Key"] = "se4-test-key-2026"

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
