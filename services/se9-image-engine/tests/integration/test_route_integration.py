"""Integration tests — validate routes parse requests correctly and call_worker receives valid params.

These tests mock ONLY worker_queue (GPU side) but exercise real request parsing, Pydantic validation,
and req_to_params conversion through the HTTP layer.
"""
import pytest
import base64
import struct
import zlib
from unittest.mock import patch, MagicMock, ANY
from app.domain.task_models import GenerationFinishReason, TaskType


@pytest.fixture
def minimal_valid_body():
    """Minimal valid body for text-to-image."""
    return {
        "prompt": "a cat sitting on a mat",
        "negative_prompt": "",
        "style_selections": ["Fooocus V2"],
        "performance_selection": "Speed",
        "aspect_ratios_selection": "1024×1024",
        "image_number": 1,
        "image_seed": 42,
        "sharpness": 2.0,
        "guidance_scale": 4.0,
        "base_model_name": "juggernautXL_v8Rundiffusion.safetensors",
        "refiner_model_name": "None",
        "refiner_switch": 0.5,
        "loras": [],
        "output_format": "png",
        "require_base64": False,
        "async_process": False,
    }


@pytest.fixture
def mock_queue_success():
    """Mock worker_queue that accepts tasks and returns immediate success."""
    mock = MagicMock()
    task = MagicMock()
    task.job_id = "test-job-001"
    task.is_finished = True
    task.finish_with_error = False
    task.task_result = None
    task.finish_progress = 100
    task.task_status = None
    task.task_step_preview = None
    task.start_mills = 1000
    task.req_param = {"require_base64": False}
    mock.add_task.return_value = task
    return mock


@pytest.fixture
def mock_blocking_result():
    """Mock blocking_get_task_result to return a success result."""
    mock = MagicMock()
    result = MagicMock()
    result.im = "2026-01-01/test.png"
    result.seed = "42"
    result.finish_reason = GenerationFinishReason.SUCCESS
    mock.return_value = [result]
    return mock


class TestV1TextToImageIntegration:
    """Test V1 text-to-image with real request parsing."""

    def test_req_to_params_called_with_correct_type(self, client, auth_header, minimal_valid_body, mock_queue_success, mock_blocking_result):
        with patch("app.services.worker.worker_queue", mock_queue_success), \
             patch("app.services.worker.blocking_get_task_result", mock_blocking_result):
            resp = client.post(
                "/v1/generation/text-to-image",
                headers={**auth_header, "content-type": "application/json"},
                json=minimal_valid_body,
            )
        assert resp.status_code == 200
        mock_queue_success.add_task.assert_called_once()
        call_args = mock_queue_success.add_task.call_args
        task_type = call_args[0][0]
        params = call_args[0][1]
        assert task_type == TaskType.TEXT_TO_IMAGE
        assert params["prompt"] == "a cat sitting on a mat"
        assert params["image_seed"] == 42

    def test_missing_prompt_returns_error(self, client, auth_header):
        resp = client.post(
            "/v1/generation/text-to-image",
            headers={**auth_header, "content-type": "application/json"},
            json={"style_selections": []},
        )
        assert resp.status_code in (422, 500)

    def test_empty_prompt_returns_error(self, client, auth_header):
        resp = client.post(
            "/v1/generation/text-to-image",
            headers={**auth_header, "content-type": "application/json"},
            json={"prompt": ""},
        )
        assert resp.status_code in (422, 500)

    def test_seed_randomization_when_minus_one(self, client, auth_header, minimal_valid_body, mock_queue_success, mock_blocking_result):
        minimal_valid_body["image_seed"] = -1
        with patch("app.services.worker.worker_queue", mock_queue_success), \
             patch("app.services.worker.blocking_get_task_result", mock_blocking_result):
            resp = client.post(
                "/v1/generation/text-to-image",
                headers={**auth_header, "content-type": "application/json"},
                json=minimal_valid_body,
            )
        assert resp.status_code == 200
        params = mock_queue_success.add_task.call_args[0][1]
        assert params["image_seed"] != -1
        assert params["image_seed"] >= 0

    def test_async_process_returns_dict(self, client, auth_header, minimal_valid_body, mock_queue_success):
        """Async mode returns a job status dict. Note: route response_model=List[GeneratedImageResult]
        doesn't match the async return shape — FastAPI returns 500. This documents the mismatch."""
        minimal_valid_body["async_process"] = True
        mock_queue_success.add_task.return_value.start_mills = 0
        mock_queue_success.add_task.return_value.is_finished = False
        mock_queue_success.add_task.return_value.task_type.value = "Text to Image"
        with patch("app.services.worker.worker_queue", mock_queue_success):
            resp = client.post(
                "/v1/generation/text-to-image",
                headers={**auth_header, "content-type": "application/json"},
                json=minimal_valid_body,
            )
        # Async returns dict (no response_model constraint)
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["job_stage"] == "WAITING"


class TestV1ImageRoutesIntegration:
    """Test V1 image routes with real request parsing + image decode."""

    def test_upscale_vary_parses_image(self, client, auth_header, sample_png, mock_queue_success, mock_blocking_result):
        b64 = base64.b64encode(sample_png).decode()
        body = {
            "prompt": "",
            "input_image": f"data:image/png;base64,{b64}",
            "uov_method": "Upscale (1.5x)",
            "style_selections": ["Fooocus V2"],
            "performance_selection": "Speed",
            "aspect_ratios_selection": "1024×1024",
            "image_number": 1,
            "image_seed": 42,
            "sharpness": 2.0,
            "guidance_scale": 4.0,
            "base_model_name": "juggernautXL_v8Rundiffusion.safetensors",
            "refiner_model_name": "None",
            "refiner_switch": 0.5,
            "loras": [],
            "output_format": "png",
            "require_base64": False,
            "async_process": False,
        }
        with patch("app.services.worker.worker_queue", mock_queue_success), \
             patch("app.services.worker.blocking_get_task_result", mock_blocking_result):
            resp = client.post(
                "/v1/generation/image-upscale-vary",
                headers={**auth_header, "content-type": "application/json"},
                json=body,
            )
        assert resp.status_code == 200
        params = mock_queue_success.add_task.call_args[0][1]
        assert params["uov_method"] == "Upscale (1.5x)"

    def test_inpaint_outpaint_task_type(self, client, auth_header, sample_png, mock_queue_success, mock_blocking_result):
        b64 = base64.b64encode(sample_png).decode()
        body = {
            "prompt": "fill the area",
            "input_image": f"data:image/png;base64,{b64}",
            "input_mask": f"data:image/png;base64,{b64}",
            "outpaint_selections": ["Right"],
            "style_selections": ["Fooocus V2"],
            "performance_selection": "Speed",
            "aspect_ratios_selection": "1024×1024",
            "image_number": 1,
            "image_seed": 42,
            "sharpness": 2.0,
            "guidance_scale": 4.0,
            "base_model_name": "juggernautXL_v8Rundiffusion.safetensors",
            "refiner_model_name": "None",
            "refiner_switch": 0.5,
            "loras": [],
            "output_format": "png",
            "require_base64": False,
            "async_process": False,
        }
        with patch("app.services.worker.worker_queue", mock_queue_success), \
             patch("app.services.worker.blocking_get_task_result", mock_blocking_result):
            resp = client.post(
                "/v1/generation/image-inpaint-outpaint",
                headers={**auth_header, "content-type": "application/json"},
                json=body,
            )
        assert resp.status_code == 200
        task_type = mock_queue_success.add_task.call_args[0][0]
        assert task_type == TaskType.IMG_INPAINT_OUTPAINT


class TestV2RoutesIntegration:
    """Test V2 routes with real Pydantic model parsing."""

    def test_v2_text_to_image_ip_parses_model(self, client, auth_header, minimal_valid_body, mock_queue_success, mock_blocking_result):
        minimal_valid_body["image_prompts"] = [{"cn_img": None, "cn_weight": 1.0}]
        with patch("app.services.worker.worker_queue", mock_queue_success), \
             patch("app.services.worker.blocking_get_task_result", mock_blocking_result):
            resp = client.post(
                "/v2/generation/text-to-image-with-ip",
                headers={**auth_header, "content-type": "application/json"},
                json=minimal_valid_body,
            )
        assert resp.status_code == 200
        params = mock_queue_success.add_task.call_args[0][1]
        assert len(params["image_prompts"]) == 5

    def test_v2_upscale_vary_task_type(self, client, auth_header, minimal_valid_body, mock_queue_success, mock_blocking_result):
        minimal_valid_body["uov_method"] = "Upscale (1.5x)"
        with patch("app.services.worker.worker_queue", mock_queue_success), \
             patch("app.services.worker.blocking_get_task_result", mock_blocking_result):
            resp = client.post(
                "/v2/generation/image-upscale-vary",
                headers={**auth_header, "content-type": "application/json"},
                json=minimal_valid_body,
            )
        assert resp.status_code == 200
        task_type = mock_queue_success.add_task.call_args[0][0]
        assert task_type == TaskType.IMG_UPSCALE_VARY

    def test_v2_enhance_task_type(self, client, auth_header, minimal_valid_body, mock_queue_success, mock_blocking_result):
        with patch("app.services.worker.worker_queue", mock_queue_success), \
             patch("app.services.worker.blocking_get_task_result", mock_blocking_result):
            resp = client.post(
                "/v2/generation/image-enhance",
                headers={**auth_header, "content-type": "application/json"},
                json=minimal_valid_body,
            )
        assert resp.status_code == 200
        task_type = mock_queue_success.add_task.call_args[0][0]
        assert task_type == TaskType.IMG_ENHANCE


class TestQueryRoutesIntegration:
    """Test query routes with real TaskQueue."""

    def test_job_queue_real_task_queue(self, client, auth_header):
        from app.services.task_queue import TaskQueue
        real_queue = TaskQueue(queue_size=10, history_size=5)
        with patch("app.services.worker.worker_queue", real_queue):
            resp = client.get("/v1/generation/job-queue", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert "finished_size" in data
        assert data["finished_size"] == 0

    def test_query_job_not_found(self, client, auth_header):
        from app.services.task_queue import TaskQueue
        real_queue = TaskQueue(queue_size=10, history_size=5)
        with patch("app.services.worker.worker_queue", real_queue):
            resp = client.get("/v1/generation/query-job?job_id=nonexistent", headers=auth_header)
        assert resp.status_code in (200, 404)

    def test_job_history_empty(self, client, auth_header):
        from app.services.task_queue import TaskQueue
        real_queue = TaskQueue(queue_size=10, history_size=5)
        with patch("app.services.worker.worker_queue", real_queue):
            resp = client.get("/v1/generation/job-history", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["history"] == []


class TestAuthIntegration:
    """Test auth middleware behavior."""

    def test_health_endpoints_exempt_from_auth(self, client):
        for path in ["/", "/health", "/ping"]:
            resp = client.get(path)
            assert resp.status_code == 200, f"{path} should not require auth"

    def test_protected_endpoint_without_key(self, client):
        resp = client.get("/v1/engines/all-models")
        assert resp.status_code == 401

    def test_protected_endpoint_wrong_key(self, client):
        resp = client.get("/v1/engines/all-models", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_protected_endpoint_valid_key(self, client, auth_header):
        resp = client.get("/v1/engines/all-models", headers=auth_header)
        assert resp.status_code == 200
