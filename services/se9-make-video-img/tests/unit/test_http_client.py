"""Unit tests for SE7 and SE8 HTTP clients."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from app.infrastructure.http_client import SE7Client, SE8Client, ServiceClient


# ---------------------------------------------------------------------------
# ServiceClient basics
# ---------------------------------------------------------------------------
def test_service_client_init_defaults():
    client = ServiceClient(base_url="http://example.com", api_key="key123", timeout=30)
    assert client.base_url == "http://example.com"
    assert client.api_key == "key123"
    assert client.timeout == 30


@pytest.mark.asyncio
async def test_request_with_retry_success():
    with respx.mock:
        route = respx.get("http://test.com/api").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client = ServiceClient(base_url="http://test.com", api_key="k", timeout=5)
        response = await client._request_with_retry("GET", "/api")
        assert response.status_code == 200
        assert route.call_count == 1
        await client.close()


@pytest.mark.asyncio
async def test_request_with_retry_eventually_fails():
    with respx.mock:
        route = respx.get("http://test.com/api").mock(
            side_effect=[
                httpx.ConnectError("connection refused"),
                httpx.ConnectError("connection refused"),
                httpx.ConnectError("connection refused"),
            ]
        )
        client = ServiceClient(base_url="http://test.com", api_key="k", timeout=5)
        with patch("app.infrastructure.http_client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.ConnectError):
                await client._request_with_retry("GET", "/api", max_retries=3)
        assert route.call_count == 3
        await client.close()


# ---------------------------------------------------------------------------
# SE7Client
# ---------------------------------------------------------------------------
class TestSE7Client:
    @pytest.fixture
    def client(self):
        return SE7Client(base_url="http://se7:8007", api_key="test-key", timeout=10)

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_job_payload(self, client):
        route = respx.post("http://se7:8007/jobs").mock(
            return_value=httpx.Response(201, json={"job_id": "abc123"})
        )
        job_id = await client.create_job(
            text="Olá mundo",
            voice_id="feminino",
            exaggeration=0.7,
            cfg_weight=0.3,
            temperature=0.9,
            normalize_text=False,
        )
        assert job_id == "abc123"

        sent_data = route.calls[0].request.content
        assert b"Ol" in sent_data or b"Ol" in route.calls[0].request.read()
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_job_uses_id_fallback(self, client):
        respx.post("http://se7:8007/jobs").mock(
            return_value=httpx.Response(201, json={"id": "fallback_id"})
        )
        job_id = await client.create_job(text="test")
        assert job_id == "fallback_id"
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_poll_job_completed(self, client):
        respx.get("http://se7:8007/jobs/poll123").mock(
            return_value=httpx.Response(200, json={"status": "completed", "id": "poll123"})
        )
        result = await client.poll_job("poll123")
        assert result["status"] == "completed"
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_poll_job_failed(self, client):
        respx.get("http://se7:8007/jobs/poll123").mock(
            return_value=httpx.Response(200, json={"status": "failed", "error": "OOM"})
        )
        with pytest.raises(Exception, match="SE7 job failed"):
            await client.poll_job("poll123")
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_poll_job_timeout(self, client):
        client.timeout = 1
        with patch("app.infrastructure.http_client.settings.se7_timeout", 1):
            respx.get("http://se7:8007/jobs/poll123").mock(
                return_value=httpx.Response(200, json={"status": "pending"})
            )
            with pytest.raises(TimeoutError, match="timed out"):
                await client.poll_job("poll123")
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_download_audio(self, client):
        respx.get("http://se7:8007/jobs/dl123/download").mock(
            return_value=httpx.Response(200, content=b"RIFF fake wav")
        )
        data = await client.download_audio("dl123")
        assert data == b"RIFF fake wav"
        await client.close()


# ---------------------------------------------------------------------------
# SE8Client
# ---------------------------------------------------------------------------
class TestSE8Client:
    @pytest.fixture
    def client(self):
        return SE8Client(base_url="http://se8:8008", api_key="test-key", timeout=10)

    @respx.mock
    @pytest.mark.asyncio
    async def test_generate_image_success(self, client):
        respx.post("http://se8:8008/v1/generation/text-to-image").mock(
            return_value=httpx.Response(200, json=[{"url": "/files/img.png"}])
        )
        result = await client.generate_image(prompt="a sunset", width=1024, height=1024)
        assert len(result) == 1
        assert result[0]["url"] == "/files/img.png"
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_generate_image_not_list(self, client):
        respx.post("http://se8:8008/v1/generation/text-to-image").mock(
            return_value=httpx.Response(200, json={"error": "bad"})
        )
        with pytest.raises(ValueError, match="unexpected format"):
            await client.generate_image(prompt="test")
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_generate_image_empty(self, client):
        respx.post("http://se8:8008/v1/generation/text-to-image").mock(
            return_value=httpx.Response(200, json=[])
        )
        with pytest.raises(ValueError, match="empty image list"):
            await client.generate_image(prompt="test")
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_download_image(self, client):
        respx.get("http://se8:8008/files/2026/img.png").mock(
            return_value=httpx.Response(200, content=b"\x89PNG fake")
        )
        data = await client.download_image("/files/2026/img.png")
        assert data == b"\x89PNG fake"
        await client.close()
