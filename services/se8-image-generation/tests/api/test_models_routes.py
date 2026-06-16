import pytest
import httpx
import respx


class TestEngines:
    @respx.mock
    def test_all_models(self, client, mock_fooocus, auth_header):
        mock_fooocus.get("/v1/engines/all-models").mock(
            return_value=httpx.Response(200, json={"model_filenames": ["model.safetensors"], "lora_filenames": ["lora.safetensors"]})
        )
        resp = client.get("/v1/engines/all-models", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert "model_filenames" in data
        assert len(data["model_filenames"]) == 1

    @respx.mock
    def test_styles(self, client, mock_fooocus, auth_header):
        mock_fooocus.get("/v1/engines/styles").mock(
            return_value=httpx.Response(200, json=["Fooocus V2", "Fooocus Enhance"])
        )
        resp = client.get("/v1/engines/styles", headers=auth_header)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @respx.mock
    def test_styles_detail(self, client, mock_fooocus, auth_header):
        mock_fooocus.get("/v1/engines/styles-detail").mock(
            return_value=httpx.Response(200, json=[{"name": "Fooocus V2", "prompt": "{prompt}", "negative_prompt": ""}])
        )
        resp = client.get("/v1/engines/styles-detail", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json()[0]["name"] == "Fooocus V2"

    @respx.mock
    def test_clean_vram(self, client, mock_fooocus, auth_header):
        mock_fooocus.get("/v1/engines/clean_vram").mock(
            return_value=httpx.Response(200, json={"message": "ok"})
        )
        resp = client.get("/v1/engines/clean_vram", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json()["message"] == "ok"

    @respx.mock
    def test_all_models_error(self, client, mock_fooocus, auth_header):
        mock_fooocus.get("/v1/engines/all-models").mock(
            return_value=httpx.Response(500, text="error")
        )
        resp = client.get("/v1/engines/all-models", headers=auth_header)
        assert resp.status_code == 500
