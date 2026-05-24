import pytest


@pytest.mark.unit
class TestModelRoutes:
    def test_model_status(self, client, mock_processor):
        mock_processor.get_model_status.return_value = {"loaded": False, "engine": "faster-whisper"}
        response = client.get("/model/status")
        assert response.status_code == 200