import pytest
from unittest.mock import MagicMock
from common.job_utils.models import JobStatus


@pytest.mark.unit
class TestJobsRoutes:
    def test_list_jobs_returns_200(self, client):
        response = client.get("/jobs")
        assert response.status_code == 200

    def test_get_job_not_found(self, client, mock_job_store):
        mock_job_store.get_job.return_value = None
        response = client.get("/jobs/nonexistent")
        assert response.status_code == 404

    def test_create_job_missing_url(self, client):
        response = client.post("/jobs", json={})
        assert response.status_code == 422