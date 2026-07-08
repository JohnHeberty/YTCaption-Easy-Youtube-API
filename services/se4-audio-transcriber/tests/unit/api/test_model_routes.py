import pytest


@pytest.mark.unit
class TestModelRoutes:
    @pytest.fixture(autouse=True)
    def _set_api_key(self, client):
        """Add API key to client headers."""
        client.headers["X-API-Key"] = "se4-test-key-2026"

    def test_model_status(self, client, mock_processor):
        mock_processor.get_model_status.return_value = {"loaded": False, "engine": "faster-whisper"}
        response = client.get("/model/status")
        assert response.status_code == 200