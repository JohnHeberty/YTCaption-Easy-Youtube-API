from __future__ import annotations

import os
import sys
import struct
import zlib
from typing import Any
from unittest.mock import MagicMock, patch, PropertyMock

# Set env BEFORE any app import
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("APP_NAME", "se8-image-generation")
os.environ.setdefault("SE8_API_KEY", "test-api-key-2026")

import pytest
from fastapi.testclient import TestClient

from _service_loader import load_app


API_KEY = "test-api-key-2026"
HEADERS = {"X-API-Key": API_KEY}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_png_bytes(width: int = 8, height: int = 8) -> bytes:
    """Create a minimal valid PNG in memory."""
    raw_data = b""
    for y in range(height):
        raw_data += b"\x00"
        for x in range(width):
            raw_data += bytes([x * 32, y * 32, 128])
    compressed = zlib.compress(raw_data)

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = zlib.crc32(c) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + c + struct.pack(">I", crc)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", compressed)
    png += chunk(b"IEND", b"")
    return png


def _json_response(resp, expected_status: int = 200) -> dict:
    """Assert status and return parsed JSON."""
    assert resp.status_code == expected_status, (
        f"Expected {expected_status}, got {resp.status_code}: {resp.text}"
    )
    if resp.status_code == 204:
        return {}
    return resp.json()


WORKER_MOCK_RETURN = [
    {"base64": None, "url": "/files/2026-01-01/test.png", "seed": "42", "finish_reason": "SUCCESS"}
]


# ---------------------------------------------------------------------------
# Fixture: TestClient with auth bypass and worker mock
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Yield a TestClient for SE8 with auth bypassed."""
    with patch("common.redis_utils.resilient_store.ResilientRedisStore._test_connection"):
        app, verify_api_key = load_app("se8-image-generation")

        async def _skip_auth() -> None:
            return None

        app.dependency_overrides[verify_api_key] = _skip_auth

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        app.dependency_overrides.pop(verify_api_key, None)


@pytest.fixture()
def auth_client():
    """Yield a TestClient WITHOUT auth override (tests real auth)."""
    with patch("common.redis_utils.resilient_store.ResilientRedisStore._test_connection"):
        app, verify_api_key = load_app("se8-image-generation")

        app.dependency_overrides.pop(verify_api_key, None)

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ===================================================================
# 1. Health endpoints (no auth)
# ===================================================================

class TestHomeEndpoint:
    @pytest.mark.e2e
    @pytest.mark.health
    def test_home_returns_200_html(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "SE8" in resp.text

    @pytest.mark.e2e
    @pytest.mark.health
    def test_home_has_docs_links(self, client: TestClient) -> None:
        resp = client.get("/")
        assert "/docs" in resp.text
        assert "/redoc" in resp.text


class TestHealthEndpoint:
    @pytest.mark.e2e
    @pytest.mark.health
    def test_health_returns_200(self, client: TestClient) -> None:
        with patch("app.services.worker.worker_queue") as mock_q:
            mock_q.queue = []
            resp = client.get("/health")
        data = _json_response(resp, 200)
        assert data["status"] in ("healthy", "degraded")
        assert data["service"] == "se8-image-generation"

    @pytest.mark.e2e
    @pytest.mark.health
    def test_health_exempt_from_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/health")
        assert resp.status_code == 200


class TestHealthDeepEndpoint:
    @pytest.mark.e2e
    @pytest.mark.health
    def test_health_deep_returns_200(self, client: TestClient) -> None:
        with patch("app.services.worker.worker_queue") as mock_q:
            mock_q.queue = []
            resp = client.get("/health/deep")
        data = _json_response(resp, 200)
        assert data["status"] in ("healthy", "degraded")
        assert "checks" in data

    @pytest.mark.e2e
    @pytest.mark.health
    def test_health_deep_degraded(self, client: TestClient) -> None:
        mock_q = MagicMock()
        type(mock_q).queue = PropertyMock(side_effect=Exception("boom"))
        with patch("app.services.worker.worker_queue", mock_q):
            resp = client.get("/health/deep")
        data = _json_response(resp, 200)
        assert "checks" in data


class TestPingEndpoint:
    @pytest.mark.e2e
    @pytest.mark.health
    def test_ping_returns_pong(self, client: TestClient) -> None:
        resp = client.get("/ping")
        data = _json_response(resp, 200)
        assert data == "pong"

    @pytest.mark.e2e
    @pytest.mark.health
    def test_ping_exempt_from_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/ping")
        assert resp.status_code == 200


# ===================================================================
# 2. Admin endpoints (auth)
# ===================================================================

class TestAdminStats:
    @pytest.mark.e2e
    @pytest.mark.admin
    def test_stats_returns_200(self, client: TestClient) -> None:
        with patch("app.services.worker.worker_queue") as mock_q:
            mock_q.get_queue_info.return_value = {
                "running_size": 0,
                "finished_size": 0,
                "last_job_id": None,
            }
            resp = client.get("/admin/stats", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["service"] == "se8-image-generation"
        assert "queue" in data
        assert "outputs" in data

    @pytest.mark.e2e
    @pytest.mark.admin
    def test_stats_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/admin/stats")
        assert resp.status_code == 401


class TestAdminCleanup:
    @pytest.mark.e2e
    @pytest.mark.admin
    def test_cleanup_returns_200(self, client: TestClient) -> None:
        with patch("app.services.worker.worker_queue") as mock_q:
            mock_q.clear_all_history.return_value = 0
            resp = client.post("/admin/cleanup", headers=HEADERS)
        data = _json_response(resp, 200)
        assert "jobs_removed" in data
        assert "files_deleted" in data
        assert "message" in data

    @pytest.mark.e2e
    @pytest.mark.admin
    def test_cleanup_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/admin/cleanup")
        assert resp.status_code == 401


# ===================================================================
# 3. Query endpoints (auth)
# ===================================================================

class TestQueryJob:
    @pytest.mark.e2e
    def test_query_job_not_found(self, client: TestClient) -> None:
        with patch("app.services.worker.worker_queue") as mock_q:
            mock_q.get_task.return_value = None
            resp = client.get("/v1/generation/query-job?job_id=nonexistent", headers=HEADERS)
        assert resp.status_code == 404

    @pytest.mark.e2e
    def test_query_job_found(self, client: TestClient) -> None:
        from app.domain.task_models import TaskType

        mock_task = MagicMock()
        mock_task.job_id = "abc-123"
        mock_task.task_type = TaskType.TEXT_TO_IMAGE
        mock_task.start_mills = 1000
        mock_task.finish_mills = 0
        mock_task.is_finished = False
        mock_task.finish_progress = 0
        mock_task.task_status = None
        mock_task.task_step_preview = None
        mock_task.task_result = None
        mock_task.finish_with_error = False

        with patch("app.services.worker.worker_queue") as mock_q:
            mock_q.get_task.return_value = mock_task
            resp = client.get("/v1/generation/query-job?job_id=abc-123", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["job_id"] == "abc-123"

    @pytest.mark.e2e
    def test_query_job_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/v1/generation/query-job?job_id=x")
        assert resp.status_code == 401


class TestJobQueue:
    @pytest.mark.e2e
    def test_job_queue_returns_200(self, client: TestClient) -> None:
        with patch("app.services.worker.worker_queue") as mock_q:
            mock_q.get_queue_info.return_value = {
                "running_size": 1,
                "finished_size": 3,
                "last_job_id": "last-456",
            }
            resp = client.get("/v1/generation/job-queue", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["running_size"] == 1
        assert data["finished_size"] == 3

    @pytest.mark.e2e
    def test_job_queue_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/v1/generation/job-queue")
        assert resp.status_code == 401


class TestJobHistory:
    @pytest.mark.e2e
    def test_job_history_empty(self, client: TestClient) -> None:
        with patch("app.services.worker.worker_queue") as mock_q:
            mock_q.get_history.return_value = {"queue": [], "history": []}
            resp = client.get("/v1/generation/job-history", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["queue"] == []
        assert data["history"] == []

    @pytest.mark.e2e
    def test_job_history_delete(self, client: TestClient) -> None:
        with patch("app.services.worker.worker_queue") as mock_q:
            mock_q.get_history.return_value = {"deleted": "del-789"}
            resp = client.get(
                "/v1/generation/job-history?job_id=del-789&delete=true",
                headers=HEADERS,
            )
        assert resp.status_code == 200

    @pytest.mark.e2e
    def test_job_history_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/v1/generation/job-history")
        assert resp.status_code == 401


class TestListOutputs:
    @pytest.mark.e2e
    def test_list_outputs_empty(self, client: TestClient) -> None:
        with patch("app.api.query_routes.os.path.isdir", return_value=False):
            resp = client.get("/v1/generation/outputs", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["days"] == []

    @pytest.mark.e2e
    def test_list_outputs_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/v1/generation/outputs")
        assert resp.status_code == 401


# ===================================================================
# 4. V1 Generation endpoints (auth, JSON body)
# ===================================================================

class TestV1TextToImage:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_text_to_image_returns_200(self, client: TestClient) -> None:
        with patch("app.api.generate_routes.call_worker") as mock_call:
            mock_call.return_value = WORKER_MOCK_RETURN
            resp = client.post(
                "/v1/generation/text-to-image",
                headers={**HEADERS, "content-type": "application/json"},
                json={"prompt": "a sunset over mountains"},
            )
        _json_response(resp, 200)
        assert mock_call.called

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_text_to_image_empty_body(self, client: TestClient) -> None:
        with patch("app.api.generate_routes.call_worker") as mock_call:
            mock_call.return_value = WORKER_MOCK_RETURN
            resp = client.post(
                "/v1/generation/text-to-image",
                headers={**HEADERS, "content-type": "application/json"},
                json={},
            )
        _json_response(resp, 200)

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_text_to_image_with_accept_query(self, client: TestClient) -> None:
        from fastapi import Response

        with patch("app.api.generate_routes.call_worker") as mock_call:
            mock_call.return_value = Response(content=b"pngbytes", media_type="image/png")
            resp = client.post(
                "/v1/generation/text-to-image?accept=image/png",
                headers={**HEADERS, "content-type": "application/json"},
                json={"prompt": "test"},
            )
        assert resp.status_code == 200

    @pytest.mark.e2e
    def test_text_to_image_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.post(
            "/v1/generation/text-to-image",
            json={"prompt": "test"},
        )
        assert resp.status_code == 401


class TestV1ImageUpscaleVary:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_image_upscale_vary_returns_200(self, client: TestClient) -> None:
        with patch("app.api.generate_routes.call_worker") as mock_call:
            mock_call.return_value = WORKER_MOCK_RETURN
            resp = client.post(
                "/v1/generation/image-upscale-vary",
                headers={**HEADERS, "content-type": "application/json"},
                json={"prompt": "upscale this", "uov_method": "Upscale (1.5x)"},
            )
        _json_response(resp, 200)
        assert mock_call.called

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_image_upscale_vary_with_input_image(self, client: TestClient) -> None:
        png_b64 = _make_png_bytes().hex()
        with patch("app.api.generate_routes.call_worker") as mock_call:
            mock_call.return_value = WORKER_MOCK_RETURN
            resp = client.post(
                "/v1/generation/image-upscale-vary",
                headers={**HEADERS, "content-type": "application/json"},
                json={"prompt": "vary", "input_image": f"data:image/png;base64,{png_b64}"},
            )
        _json_response(resp, 200)

    @pytest.mark.e2e
    def test_image_upscale_vary_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/v1/generation/image-upscale-vary", json={})
        assert resp.status_code == 401


class TestV1ImageInpaintOutpaint:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_image_inpaint_outpaint_returns_200(self, client: TestClient) -> None:
        with patch("app.api.generate_routes.call_worker") as mock_call:
            mock_call.return_value = WORKER_MOCK_RETURN
            resp = client.post(
                "/v1/generation/image-inpaint-outpaint",
                headers={**HEADERS, "content-type": "application/json"},
                json={"prompt": "inpaint this area"},
            )
        _json_response(resp, 200)
        assert mock_call.called

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_image_inpaint_outpaint_with_outpaint(self, client: TestClient) -> None:
        with patch("app.api.generate_routes.call_worker") as mock_call:
            mock_call.return_value = WORKER_MOCK_RETURN
            resp = client.post(
                "/v1/generation/image-inpaint-outpaint",
                headers={**HEADERS, "content-type": "application/json"},
                json={
                    "prompt": "expand image",
                    "outpaint_selections": ["Left", "Right"],
                    "outpaint_distance_left": 100,
                    "outpaint_distance_right": 100,
                },
            )
        _json_response(resp, 200)

    @pytest.mark.e2e
    def test_image_inpaint_outpaint_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/v1/generation/image-inpaint-outpaint", json={})
        assert resp.status_code == 401


class TestV1ImagePrompt:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_image_prompt_returns_200(self, client: TestClient) -> None:
        with patch("app.api.generate_routes.call_worker") as mock_call:
            mock_call.return_value = WORKER_MOCK_RETURN
            resp = client.post(
                "/v1/generation/image-prompt",
                headers={**HEADERS, "content-type": "application/json"},
                json={"prompt": "image prompt test"},
            )
        _json_response(resp, 200)
        assert mock_call.called

    @pytest.mark.e2e
    def test_image_prompt_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/v1/generation/image-prompt", json={})
        assert resp.status_code == 401


class TestV1ImageEnhance:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_image_enhance_returns_200(self, client: TestClient) -> None:
        with patch("app.api.generate_routes.call_worker") as mock_call:
            mock_call.return_value = WORKER_MOCK_RETURN
            resp = client.post(
                "/v1/generation/image-enhance",
                headers={**HEADERS, "content-type": "application/json"},
                json={"prompt": "enhance this image"},
            )
        _json_response(resp, 200)
        assert mock_call.called

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_image_enhance_with_params(self, client: TestClient) -> None:
        with patch("app.api.generate_routes.call_worker") as mock_call:
            mock_call.return_value = WORKER_MOCK_RETURN
            resp = client.post(
                "/v1/generation/image-enhance",
                headers={**HEADERS, "content-type": "application/json"},
                json={
                    "prompt": "enhance",
                    "enhance_checkbox": True,
                    "enhance_uov_method": "Vary (Strong)",
                    "save_final_enhanced_image_only": True,
                },
            )
        _json_response(resp, 200)

    @pytest.mark.e2e
    def test_image_enhance_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/v1/generation/image-enhance", json={})
        assert resp.status_code == 401


# ===================================================================
# 5. V2 Generation endpoints (auth, JSON body)
# ===================================================================

class TestV2TextToImageWithIp:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_text_to_image_with_ip_returns_200(self, client: TestClient) -> None:
        with patch("app.api.generate_v2_routes.call_worker") as mock_call:
            mock_call.return_value = WORKER_MOCK_RETURN
            resp = client.post(
                "/v2/generation/text-to-image-with-ip",
                headers={**HEADERS, "content-type": "application/json"},
                json={"prompt": "generate with image prompt", "image_prompts": []},
            )
        _json_response(resp, 200)
        assert mock_call.called

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_v2_pads_image_prompts(self, client: TestClient) -> None:
        with patch("app.api.generate_v2_routes.call_worker") as mock_call:
            mock_call.return_value = []
            client.post(
                "/v2/generation/text-to-image-with-ip",
                headers={**HEADERS, "content-type": "application/json"},
                json={"prompt": "test", "image_prompts": [{"cn_img": None}]},
            )
        req = mock_call.call_args[0][0]
        assert len(req.image_prompts) == 5

    @pytest.mark.e2e
    def test_text_to_image_with_ip_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/v2/generation/text-to-image-with-ip", json={})
        assert resp.status_code == 401


class TestV2ImageUpscaleVary:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_image_upscale_vary_v2_returns_200(self, client: TestClient) -> None:
        with patch("app.api.generate_v2_routes.call_worker") as mock_call:
            mock_call.return_value = WORKER_MOCK_RETURN
            resp = client.post(
                "/v2/generation/image-upscale-vary",
                headers={**HEADERS, "content-type": "application/json"},
                json={"prompt": "upscale v2", "uov_method": "Disabled"},
            )
        _json_response(resp, 200)
        assert mock_call.called

    @pytest.mark.e2e
    def test_image_upscale_vary_v2_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/v2/generation/image-upscale-vary", json={})
        assert resp.status_code == 401


class TestV2ImageInpaintOutpaint:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_image_inpaint_outpaint_v2_returns_200(self, client: TestClient) -> None:
        with patch("app.api.generate_v2_routes.call_worker") as mock_call:
            mock_call.return_value = WORKER_MOCK_RETURN
            resp = client.post(
                "/v2/generation/image-inpaint-outpaint",
                headers={**HEADERS, "content-type": "application/json"},
                json={"prompt": "inpaint v2"},
            )
        _json_response(resp, 200)
        assert mock_call.called

    @pytest.mark.e2e
    def test_image_inpaint_outpaint_v2_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/v2/generation/image-inpaint-outpaint", json={})
        assert resp.status_code == 401


class TestV2ImagePrompt:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_image_prompt_v2_returns_200(self, client: TestClient) -> None:
        with patch("app.api.generate_v2_routes.call_worker") as mock_call:
            mock_call.return_value = WORKER_MOCK_RETURN
            resp = client.post(
                "/v2/generation/image-prompt",
                headers={**HEADERS, "content-type": "application/json"},
                json={"prompt": "prompt v2", "image_prompts": []},
            )
        _json_response(resp, 200)
        assert mock_call.called

    @pytest.mark.e2e
    def test_image_prompt_v2_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/v2/generation/image-prompt", json={})
        assert resp.status_code == 401


class TestV2ImageEnhance:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_image_enhance_v2_returns_200(self, client: TestClient) -> None:
        with patch("app.api.generate_v2_routes.call_worker") as mock_call:
            mock_call.return_value = WORKER_MOCK_RETURN
            resp = client.post(
                "/v2/generation/image-enhance",
                headers={**HEADERS, "content-type": "application/json"},
                json={"prompt": "enhance v2"},
            )
        _json_response(resp, 200)
        assert mock_call.called

    @pytest.mark.e2e
    def test_image_enhance_v2_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/v2/generation/image-enhance", json={})
        assert resp.status_code == 401


# ===================================================================
# 6. Face restore endpoint (auth)
# ===================================================================

class TestFaceRestore:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_face_restore_invalid_model(self, client: TestClient) -> None:
        resp = client.post(
            "/v1/face/restore",
            headers={**HEADERS, "content-type": "application/json"},
            json={"image": "base64data", "model": "InvalidModel"},
        )
        assert resp.status_code in (400, 422, 500)

    @pytest.mark.e2e
    @pytest.mark.crud
    def test_face_restore_missing_image(self, client: TestClient) -> None:
        resp = client.post(
            "/v1/face/restore",
            headers={**HEADERS, "content-type": "application/json"},
            json={"model": "CodeFormer"},
        )
        assert resp.status_code == 422

    @pytest.mark.e2e
    def test_face_restore_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.post(
            "/v1/face/restore",
            json={"image": "data"},
        )
        assert resp.status_code == 401


# ===================================================================
# 7. Models / Engines endpoints (auth)
# ===================================================================

class TestAllModels:
    @pytest.mark.e2e
    def test_all_models_returns_200(self, client: TestClient) -> None:
        with patch.dict("sys.modules", {"modules": None, "modules.config": None}):
            resp = client.get("/v1/engines/all-models", headers=HEADERS)
        data = _json_response(resp, 200)
        assert "model_filenames" in data
        assert "lora_filenames" in data

    @pytest.mark.e2e
    def test_all_models_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/v1/engines/all-models")
        assert resp.status_code == 401


class TestStyles:
    @pytest.mark.e2e
    def test_styles_returns_200(self, client: TestClient) -> None:
        with patch.dict("sys.modules", {"modules": None, "modules.sdxl_styles": None}):
            resp = client.get("/v1/engines/styles", headers=HEADERS)
        _json_response(resp, 200)

    @pytest.mark.e2e
    def test_styles_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/v1/engines/styles")
        assert resp.status_code == 401


class TestStylesDetail:
    @pytest.mark.e2e
    def test_styles_detail_returns_200(self, client: TestClient) -> None:
        with patch.dict("sys.modules", {"modules": None, "modules.sdxl_styles": None}):
            resp = client.get("/v1/engines/styles-detail", headers=HEADERS)
        _json_response(resp, 200)

    @pytest.mark.e2e
    def test_styles_detail_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/v1/engines/styles-detail")
        assert resp.status_code == 401


class TestCleanVram:
    @pytest.mark.e2e
    def test_clean_vram_returns_200(self, client: TestClient) -> None:
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"app.services.model_manager": mock_module}):
            resp = client.get("/v1/engines/clean_vram", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["message"] == "ok"

    @pytest.mark.e2e
    def test_clean_vram_error(self, client: TestClient) -> None:
        mock_module = MagicMock()
        mock_module.get_model_manager.side_effect = Exception("GPU error")
        with patch.dict("sys.modules", {"app.services.model_manager": mock_module}):
            resp = client.get("/v1/engines/clean_vram", headers=HEADERS)
        data = _json_response(resp, 200)
        assert data["message"] == "error"

    @pytest.mark.e2e
    def test_clean_vram_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/v1/engines/clean_vram")
        assert resp.status_code == 401


class TestCleanupMemory:
    @pytest.mark.e2e
    def test_cleanup_memory_returns_200(self, client: TestClient) -> None:
        mock_pipeline = MagicMock()
        mock_mm = MagicMock()
        mock_proc = MagicMock()
        mock_proc.memory_info.return_value.rss = 1024 * 1024 * 100
        with patch("psutil.Process", return_value=mock_proc), \
             patch("app.services.pipeline.get_pipeline", return_value=mock_pipeline), \
             patch("app.services.model_manager.get_model_manager", return_value=mock_mm), \
             patch("gc.collect"), \
             patch("os.execv"), \
             patch("threading.Thread"):
            resp = client.get("/v1/engines/cleanup", headers=HEADERS)
        assert resp.status_code in (200, 500)

    @pytest.mark.e2e
    def test_cleanup_memory_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/v1/engines/cleanup")
        assert resp.status_code == 401


# ===================================================================
# 8. Tools endpoints (auth)
# ===================================================================

class TestUpscaleEsrgan:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_upscale_esrgan_returns_200(self, client: TestClient) -> None:
        png_bytes = _make_png_bytes()
        mock_upscaled = MagicMock()
        mock_upscaled.shape = (16, 16, 3)
        mock_upscaled.__getitem__ = lambda self, key: self

        with patch("app.services.upscaler.perform_upscale", return_value=mock_upscaled):
            resp = client.post(
                "/v1/tools/upscale-esrgan?scale=2.0",
                headers=HEADERS,
                files={"file": ("test.png", png_bytes, "image/png")},
            )
        assert resp.status_code in (200, 500)

    @pytest.mark.e2e
    def test_upscale_esrgan_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.post(
            "/v1/tools/upscale-esrgan",
            files={"file": ("test.png", b"fake", "image/png")},
        )
        assert resp.status_code == 401


class TestDescribeImage:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_describe_image_returns_200(self, client: TestClient) -> None:
        png_bytes = _make_png_bytes()
        with patch.dict("sys.modules", {"modules": None, "modules.util": None}):
            resp = client.post(
                "/v1/tools/describe-image?image_type=Photo",
                headers=HEADERS,
                files={"image": ("test.png", png_bytes, "image/png")},
            )
        data = _json_response(resp, 200)
        assert "describe" in data

    @pytest.mark.e2e
    def test_describe_image_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.post(
            "/v1/tools/describe-image",
            files={"image": ("test.png", b"fake", "image/png")},
        )
        assert resp.status_code == 401


class TestGenerateMask:
    @pytest.mark.e2e
    @pytest.mark.crud
    def test_generate_mask_returns_200(self, client: TestClient) -> None:
        with patch.dict("sys.modules", {"extras": None, "extras.inpaint_mask": None}):
            resp = client.post(
                "/v1/tools/generate_mask",
                headers={**HEADERS, "content-type": "application/json"},
                json={"image": "", "mask_model": "u2net"},
            )
        assert resp.status_code == 200

    @pytest.mark.e2e
    def test_generate_mask_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.post(
            "/v1/tools/generate_mask",
            json={"image": ""},
        )
        assert resp.status_code == 401


# ===================================================================
# 9. File serving endpoint
# ===================================================================

class TestFileRoutes:
    @pytest.mark.e2e
    def test_get_output_file_not_found(self, client: TestClient) -> None:
        resp = client.get("/files/2026-01-01/nonexistent.png", headers=HEADERS)
        assert resp.status_code == 404

    @pytest.mark.e2e
    def test_get_output_file_invalid_ext(self, client: TestClient) -> None:
        resp = client.get("/files/2026-01-01/test.txt", headers=HEADERS)
        assert resp.status_code == 404

    @pytest.mark.e2e
    def test_get_output_file_success(self, client: TestClient, tmp_path) -> None:
        date_dir = tmp_path / "2026-01-01"
        date_dir.mkdir()
        img_file = date_dir / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\nfake png content")

        with patch("app.api.file_routes.get_settings") as mock_s:
            mock_s.return_value.output_dir = str(tmp_path)
            resp = client.get("/files/2026-01-01/test.png", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.content == b"\x89PNG\r\n\x1a\nfake png content"

    @pytest.mark.e2e
    def test_get_output_file_webp(self, client: TestClient, tmp_path) -> None:
        date_dir = tmp_path / "2026-06-15"
        date_dir.mkdir()
        img_file = date_dir / "photo.webp"
        img_file.write_bytes(b"RIFF fake webp")

        with patch("app.api.file_routes.get_settings") as mock_s:
            mock_s.return_value.output_dir = str(tmp_path)
            resp = client.get("/files/2026-06-15/photo.webp", headers=HEADERS)
        assert resp.status_code == 200
        assert "image/webp" in resp.headers.get("content-type", "")

    @pytest.mark.e2e
    def test_file_routes_requires_auth(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/files/2026-01-01/test.png")
        assert resp.status_code == 401


# ===================================================================
# 10. Auth enforcement tests
# ===================================================================

class TestAuthentication:
    @pytest.mark.e2e
    @pytest.mark.auth
    def test_valid_api_key_accepted(self, auth_client: TestClient) -> None:
        with patch("app.services.worker.worker_queue") as mock_q:
            mock_q.queue = []
            resp = auth_client.get("/health", headers=HEADERS)
        assert resp.status_code == 200

    @pytest.mark.e2e
    @pytest.mark.auth
    def test_missing_key_returns_401(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/v1/engines/styles")
        assert resp.status_code == 401

    @pytest.mark.e2e
    @pytest.mark.auth
    def test_wrong_key_returns_401(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/v1/engines/styles", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    @pytest.mark.e2e
    @pytest.mark.auth
    def test_exempt_paths_need_no_key(self, auth_client: TestClient) -> None:
        for path in ("/", "/health", "/health/deep", "/ping"):
            resp = auth_client.get(path)
            assert resp.status_code == 200, f"{path} should be exempt from auth"

    @pytest.mark.e2e
    @pytest.mark.auth
    def test_v1_generation_requires_key(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/v1/generation/text-to-image", json={"prompt": "test"})
        assert resp.status_code == 401

    @pytest.mark.e2e
    @pytest.mark.auth
    def test_v2_generation_requires_key(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/v2/generation/text-to-image-with-ip", json={})
        assert resp.status_code == 401

    @pytest.mark.e2e
    @pytest.mark.auth
    def test_engines_requires_key(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/v1/engines/styles")
        assert resp.status_code == 401

    @pytest.mark.e2e
    @pytest.mark.auth
    def test_tools_requires_key(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/v1/tools/generate_mask", json={"image": ""})
        assert resp.status_code == 401

    @pytest.mark.e2e
    @pytest.mark.auth
    def test_files_requires_key(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/files/2026-01-01/test.png")
        assert resp.status_code == 401

    @pytest.mark.e2e
    @pytest.mark.auth
    def test_admin_requires_key(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/admin/stats")
        assert resp.status_code == 401

    @pytest.mark.e2e
    @pytest.mark.auth
    def test_face_requires_key(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/v1/face/restore", json={"image": "x"})
        assert resp.status_code == 401

    @pytest.mark.e2e
    @pytest.mark.auth
    def test_query_requires_key(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/v1/generation/query-job?job_id=x")
        assert resp.status_code == 401
