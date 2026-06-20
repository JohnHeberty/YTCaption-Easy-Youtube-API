"""API-level test configuration."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    """TestClient for the FastAPI app."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="module")
def auth_header():
    """Auth header with valid API key."""
    return {"X-API-Key": "test-key-123"}
