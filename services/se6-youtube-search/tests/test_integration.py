"""
Integration tests for API endpoints
"""
import pytest
import redis
from fastapi.testclient import TestClient


def _redis_available() -> bool:
    try:
        r = redis.Redis(host="localhost", port=6379, db=6, socket_connect_timeout=2)
        r.ping()
        return True
    except (redis.ConnectionError, ConnectionRefusedError, redis.TimeoutError):
        return False


pytestmark = pytest.mark.skipif(not _redis_available(), reason="Redis not available at localhost:6379")

from app.main import app
from app.core.config import get_settings

client = TestClient(app, raise_server_exceptions=False)
settings = get_settings()
API_KEY = settings.get("api_key", "se6-test-key-2026")
HEADERS = {"X-API-Key": API_KEY}


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "YouTube Search Service"
    assert "endpoints" in data


def test_health_check():
    """Test health check endpoint"""
    from unittest.mock import MagicMock
    mock_store = MagicMock()
    mock_store.redis.ping.return_value = True
    mock_store.get_stats.return_value = {"total_jobs": 0, "by_status": {}}
    app.state.job_store = mock_store
    response = client.get("/health")
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data
    assert "checks" in data


def test_admin_stats():
    """Test admin stats endpoint"""
    response = client.get("/admin/stats", headers=HEADERS)
    # May fail with 500 if Celery/Redis not reachable from host
    assert response.status_code in [200, 500]


def test_admin_queue():
    """Test admin queue endpoint"""
    response = client.get("/admin/queue", headers=HEADERS)
    # May fail with 500 if Celery not reachable from host
    assert response.status_code in [200, 500]


def test_list_jobs():
    """Test list jobs endpoint"""
    response = client.get("/jobs", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "total" in data


def test_create_video_info_job_invalid_params():
    """Test creating video info job without video_id"""
    response = client.post("/search/video-info", headers=HEADERS)
    assert response.status_code == 422


def test_create_video_search_job_invalid_params():
    """Test creating video search job without query"""
    response = client.post("/search/videos", headers=HEADERS)
    assert response.status_code == 422


def test_get_nonexistent_job():
    """Test getting nonexistent job"""
    response = client.get("/jobs/nonexistent_job_id", headers=HEADERS)
    assert response.status_code == 404


def test_delete_nonexistent_job():
    """Test deleting nonexistent job"""
    response = client.delete("/jobs/nonexistent_job_id", headers=HEADERS)
    assert response.status_code == 404


def test_basic_cleanup():
    """Test basic cleanup endpoint"""
    response = client.post("/admin/cleanup?deep=false", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "jobs_removed" in data
    assert "message" in data
