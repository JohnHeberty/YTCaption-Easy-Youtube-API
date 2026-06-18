import os
import pytest
from unittest.mock import patch


class TestFileRoutes:
    def test_get_output_file_not_found(self, client, auth_header):
        resp = client.get("/files/2026-01-01/missing.png", headers=auth_header)
        assert resp.status_code == 404

    def test_get_output_file_invalid_ext(self, client, auth_header):
        resp = client.get("/files/2026-01-01/test.txt", headers=auth_header)
        assert resp.status_code == 404

    def test_get_output_file_success(self, client, auth_header, tmp_path):
        date_dir = tmp_path / "2026-01-01"
        date_dir.mkdir()
        img_file = date_dir / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\nfake png content")

        with patch("app.api.file_routes.get_settings") as mock_s:
            mock_s.return_value.output_dir = str(tmp_path)
            resp = client.get("/files/2026-01-01/test.png", headers=auth_header)
        assert resp.status_code == 200
        assert resp.content == b"\x89PNG\r\n\x1a\nfake png content"

    def test_get_output_file_webp(self, client, auth_header, tmp_path):
        date_dir = tmp_path / "2026-06-15"
        date_dir.mkdir()
        img_file = date_dir / "photo.webp"
        img_file.write_bytes(b"RIFF fake webp")

        with patch("app.api.file_routes.get_settings") as mock_s:
            mock_s.return_value.output_dir = str(tmp_path)
            resp = client.get("/files/2026-06-15/photo.webp", headers=auth_header)
        assert resp.status_code == 200
        assert "image/webp" in resp.headers.get("content-type", "")
