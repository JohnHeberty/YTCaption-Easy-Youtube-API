import pytest
from unittest.mock import patch, MagicMock
from app.domain.task_models import TaskType


class TestQueryJob:
    def test_query_job_not_found(self, client, auth_header):
        with patch("app.api.query_routes.worker_queue") as mock_q:
            mock_q.get_task.return_value = None
            resp = client.get("/v1/generation/query-job?job_id=xxx", headers=auth_header)
        assert resp.status_code == 404

    def test_query_job_found(self, client, auth_header):
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

        with patch("app.api.query_routes.worker_queue") as mock_q:
            mock_q.get_task.return_value = mock_task
            resp = client.get("/v1/generation/query-job?job_id=abc-123", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "abc-123"


class TestJobQueue:
    def test_job_queue_info(self, client, auth_header):
        with patch("app.api.query_routes.worker_queue") as mock_q:
            mock_q.get_queue_info.return_value = {
                "running_size": 2,
                "finished_size": 5,
                "last_job_id": "last-123",
            }
            resp = client.get("/v1/generation/job-queue", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["running_size"] == 2
        assert data["finished_size"] == 5


class TestJobHistory:
    def test_job_history_empty(self, client, auth_header):
        with patch("app.api.query_routes.worker_queue") as mock_q:
            mock_q.get_history.return_value = {"queue": [], "history": []}
            resp = client.get("/v1/generation/job-history", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["queue"] == []
        assert data["history"] == []

    def test_job_history_delete(self, client, auth_header):
        mock_task = MagicMock()
        mock_task.job_id = "del-123"
        with patch("app.api.query_routes.worker_queue") as mock_q:
            mock_q.get_task.return_value = mock_task
            mock_q.history = [mock_task]
            resp = client.get(
                "/v1/generation/job-history?job_id=del-123&delete=true",
                headers=auth_header,
            )
        assert resp.status_code == 200


class TestListOutputs:
    def test_list_outputs_empty(self, client, auth_header):
        with patch("app.api.query_routes.os.path.isdir", return_value=False):
            resp = client.get("/v1/generation/outputs", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == []
