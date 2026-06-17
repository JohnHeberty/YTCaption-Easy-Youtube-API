import pytest
from unittest.mock import patch, MagicMock


class TestEngines:
    def test_all_models_fallback(self, client, auth_header):
        with patch.dict("sys.modules", {"modules": None, "modules.config": None}):
            resp = client.get("/v1/engines/all-models", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_filenames"] == []
        assert data["lora_filenames"] == []

    def test_styles_fallback(self, client, auth_header):
        with patch.dict("sys.modules", {"modules": None, "modules.sdxl_styles": None}):
            resp = client.get("/v1/engines/styles", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_styles_detail_fallback(self, client, auth_header):
        with patch.dict("sys.modules", {"modules": None, "modules.sdxl_styles": None}):
            resp = client.get("/v1/engines/styles-detail", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_clean_vram(self, client, auth_header):
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"app.services.model_manager": mock_module}):
            resp = client.get("/v1/engines/clean_vram", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "ok"

    def test_clean_vram_error(self, client, auth_header):
        mock_module = MagicMock()
        mock_module.get_model_manager.side_effect = Exception("GPU error")
        with patch.dict("sys.modules", {"app.services.model_manager": mock_module}):
            resp = client.get("/v1/engines/clean_vram", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "error"
