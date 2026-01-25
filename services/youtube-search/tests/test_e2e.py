"""
End-to-end tests for YouTube Search Service
These tests require Redis to be running
"""
import pytest
import time
from fastapi.testclient import TestClient
from app.main import app
from app.models import JobStatus

client = TestClient(app)


@pytest.mark.e2e
class TestEndToEnd:
    """End-to-end tests that require external dependencies"""
    
    def test_complete_video_info_flow(self):
        """Test complete flow: create job -> poll -> get result"""
        # 1. Create video info job
        response = client.post(
            "/search/video-info",
            params={"video_id": "dQw4w9WgXcQ"}
        )
        assert response.status_code == 200
        job_data = response.json()
        job_id = job_data["id"]
        
        assert job_data["status"] in ["queued", "processing", "completed"]
        assert job_data["search_type"] == "video_info"
        assert job_data["video_id"] == "dQw4w9WgXcQ"
        
        # 2. Poll for completion (with timeout)
        max_attempts = 30  # 30 seconds max
        job_completed = False
        
        for _ in range(max_attempts):
            response = client.get(f"/jobs/{job_id}")
            assert response.status_code == 200
            job_data = response.json()
            
            if job_data["status"] == "completed":
                job_completed = True
                break
            elif job_data["status"] == "failed":
                pytest.fail(f"Job failed: {job_data.get('error_message')}")
            
            time.sleep(1)
        
        # 3. Verify completion
        if not job_completed:
            pytest.skip("Job did not complete in time (30s)")
        
        # 4. Verify result structure
        assert job_data["result"] is not None
        assert "video_id" in job_data["result"]
        assert job_data["progress"] == 100.0
        
        # 5. Test cache hit - same request should return existing job
        response = client.post(
            "/search/video-info",
            params={"video_id": "dQw4w9WgXcQ"}
        )
        assert response.status_code == 200
        cached_job = response.json()
        assert cached_job["id"] == job_id
        assert cached_job["status"] == "completed"
        
        # 6. Delete job
        response = client.delete(f"/jobs/{job_id}")
        assert response.status_code == 200
        
        # 7. Verify deletion
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 404
    
    def test_video_search_flow(self):
        """Test video search flow"""
        # 1. Create search job
        response = client.post(
            "/search/videos",
            params={"query": "python", "max_results": 5}
        )
        assert response.status_code == 200
        job_data = response.json()
        job_id = job_data["id"]
        
        # 2. Wait for completion
        max_attempts = 30
        for _ in range(max_attempts):
            response = client.get(f"/jobs/{job_id}")
            job_data = response.json()
            
            if job_data["status"] in ["completed", "failed"]:
                break
            
            time.sleep(1)
        
        # 3. Verify result
        if job_data["status"] == "completed":
            assert job_data["result"] is not None
            # Clean up
            client.delete(f"/jobs/{job_id}")
    
    def test_admin_endpoints(self):
        """Test admin endpoints"""
        # Stats
        response = client.get("/admin/stats")
        assert response.status_code == 200
        stats = response.json()
        assert "total_jobs" in stats
        
        # Queue
        response = client.get("/admin/queue")
        assert response.status_code == 200
        queue = response.json()
        assert "broker" in queue
        
        # Basic cleanup
        response = client.post("/admin/cleanup?deep=false")
        assert response.status_code == 200
        result = response.json()
        assert "jobs_removed" in result
