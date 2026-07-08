"""Unit tests for webhook notification sender."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from app.api.webhook import WEBHOOK_MAX_RETRIES, send_webhook
from app.core.models import CreateVideoRequest, NarrationSegment, VideoJob


def _make_job(webhook_url: str | None = "https://example.com/hook", **overrides) -> VideoJob:
    request = CreateVideoRequest(
        post_id="post_1",
        hook="Hook",
        estimated_seconds=30,
        narration=[NarrationSegment(t=0.0, text="text")],
        scene_suggestions=[],
        webhook_url=webhook_url,
        hashtags=["#tag1", "#tag2"],
        title_options=["Title A", "Title B"],
        **{k: v for k, v in overrides.items() if k in CreateVideoRequest.model_fields},
    )
    return VideoJob(job_id="rbg_test", post_id="post_1", request=request)


# ---------------------------------------------------------------------------
# Early return
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_no_webhook_url_returns_early():
    job = _make_job(webhook_url=None)
    with respx.mock:
        route = respx.post("https://example.com/hook").mock()
        await send_webhook(job)
        assert route.call_count == 0


@pytest.mark.asyncio
async def test_empty_webhook_url_returns_early():
    job = _make_job(webhook_url="")
    with respx.mock:
        route = respx.post("https://example.com/hook").mock()
        await send_webhook(job)
        assert route.call_count == 0


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------
@respx.mock
@pytest.mark.asyncio
async def test_payload_construction():
    job = _make_job(webhook_url="https://example.com/hook")
    route = respx.post("https://example.com/hook").mock(
        return_value=httpx.Response(200)
    )

    with patch("app.api.webhook.settings") as mock_settings:
        mock_settings.external_url = "https://cdn.example.com"
        mock_settings.port = 8009
        await send_webhook(job)

    payload = route.calls[0].request.content
    import json
    body = json.loads(payload)
    assert body["event"] == "video_ready"
    assert body["job_id"] == "rbg_test"
    assert body["post_id"] == "post_1"
    assert body["status"] == "completed"
    assert "https://cdn.example.com/download/rbg_test" in body["download_url"]
    assert body["hashtags"] == ["#tag1", "#tag2"]
    assert body["duration_seconds"] == 30


@respx.mock
@pytest.mark.asyncio
async def test_payload_with_title():
    job = _make_job(webhook_url="https://example.com/hook")
    route = respx.post("https://example.com/hook").mock(
        return_value=httpx.Response(200)
    )

    with patch("app.api.webhook.settings") as mock_settings:
        mock_settings.external_url = ""
        mock_settings.port = 8009
        await send_webhook(job)

    import json
    body = json.loads(route.calls[0].request.content)
    assert body["title"] == "Title A"


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------
@respx.mock
@pytest.mark.asyncio
async def test_retry_on_failure():
    job = _make_job(webhook_url="https://example.com/hook")
    route = respx.post("https://example.com/hook").mock(
        side_effect=[
            httpx.ConnectError("fail 1"),
            httpx.ConnectError("fail 2"),
            httpx.Response(200),
        ]
    )

    with patch("app.api.webhook.settings") as mock_settings:
        mock_settings.external_url = ""
        mock_settings.port = 8009
        with patch("app.api.webhook.asyncio.sleep", new_callable=AsyncMock):
            await send_webhook(job)

    assert route.call_count == 3


@respx.mock
@pytest.mark.asyncio
async def test_all_retries_fail_no_exception():
    job = _make_job(webhook_url="https://example.com/hook")
    route = respx.post("https://example.com/hook").mock(
        side_effect=httpx.ConnectError("down")
    )

    with patch("app.api.webhook.settings") as mock_settings:
        mock_settings.external_url = ""
        mock_settings.port = 8009
        with patch("app.api.webhook.asyncio.sleep", new_callable=AsyncMock):
            await send_webhook(job)

    assert route.call_count == WEBHOOK_MAX_RETRIES
