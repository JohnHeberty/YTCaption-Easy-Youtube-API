"""
Integration tests for API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "YouTube Search Service"
    assert "endpoints" in data


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    # Can be 200 or 503 depending on Redis availability
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data
    assert "checks" in data


def test_admin_stats():
    """Test admin stats endpoint"""
    response = client.get("/admin/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_jobs" in data


def test_admin_queue():
    """Test admin queue endpoint"""
    response = client.get("/admin/queue")
    assert response.status_code == 200
    data = response.json()
    assert "broker" in data
    assert data["broker"] == "redis"


def test_list_jobs():
    """Test list jobs endpoint"""
    response = client.get("/jobs")
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "total" in data


def test_create_video_info_job_invalid_params():
    """Test creating video info job without video_id"""
    response = client.post("/search/video-info")
    # Should fail with 422 (validation error) because video_id is required
    assert response.status_code == 422


def test_create_video_search_job_invalid_params():
    """Test creating video search job without query"""
    response = client.post("/search/videos")
    # Should fail with 422 (validation error) because query is required
    assert response.status_code == 422


def test_get_nonexistent_job():
    """Test getting nonexistent job"""
    response = client.get("/jobs/nonexistent_job_id")
    assert response.status_code == 404


def test_delete_nonexistent_job():
    """Test deleting nonexistent job"""
    response = client.delete("/jobs/nonexistent_job_id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_basic_cleanup():
    """Test basic cleanup endpoint"""
    response = client.post("/admin/cleanup?deep=false")
    assert response.status_code == 200
    data = response.json()
    assert "jobs_removed" in data
    assert "message" in data


# Note: Deep cleanup test is commented out to avoid accidentally deleting data
# @pytest.mark.asyncio
# async def test_deep_cleanup():
#     """Test deep cleanup endpoint"""
#     response = client.post("/admin/cleanup?deep=true&purge_celery_queue=false")
#     assert response.status_code == 200
#     data = response.json()
#     assert "jobs_removed" in data
#     assert "redis_flushed" in data
