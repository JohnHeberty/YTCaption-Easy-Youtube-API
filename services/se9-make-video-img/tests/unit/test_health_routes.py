from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.health_routes import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_ping(client):
    resp = client.get("/ping")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"pong": True}


def test_health_check_structure(client):
    with (
        patch("app.api.health_routes.httpx.AsyncClient") as MockClient,
        patch("app.api.health_routes.ServiceHealthChecker") as MockChecker,
    ):
        mock_instance = MockChecker.return_value
        mock_instance.check_all = AsyncMock(
            return_value={
                "status": "ok",
                "service": "make-video-img",
                "version": "0.1.0",
                "checks": {
                    "se7": {"status": "ok"},
                    "se8": {"status": "ok"},
                    "disk": {"status": "ok"},
                    "ffmpeg": {"status": "ok"},
                },
            }
        )
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "checks" in body


def test_health_check_calls_add_check(client):
    with (
        patch("app.api.health_routes.httpx.AsyncClient") as MockClient,
        patch("app.api.health_routes.ServiceHealthChecker") as MockChecker,
    ):
        mock_instance = MockChecker.return_value
        mock_instance.check_all = AsyncMock(
            return_value={"status": "ok", "service": "make-video-img", "version": "0.1.0", "checks": {}}
        )
        client.get("/health")

        check_names = [call.args[0] for call in mock_instance.add_check.call_args_list]
        assert "se7" in check_names
        assert "se8" in check_names
        assert "disk" in check_names
        assert "ffmpeg" in check_names
        assert mock_instance.add_check.call_count == 4
