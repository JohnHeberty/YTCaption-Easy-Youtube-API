"""
Mock Celery for testing.

Usage in conftest.py:
    from common.test_utils.mock_celery import mock_celery_app

    @pytest.fixture
    def celery_app():
        return mock_celery_app()
"""
from unittest.mock import MagicMock, patch


class MockCeleryTask:
    """Mock for a Celery task result."""

    def __init__(self, task_id="mock-task-id"):
        self.id = task_id
        self.status = "SUCCESS"
        self.result = None

    def get(self, timeout=None):
        return self.result

    def ready(self):
        return True

    def successful(self):
        return True


def mock_celery_app():
    """Create a mock Celery app for testing.

    Returns:
        MagicMock configured as a Celery app
    """
    app = MagicMock()
    app.control = MagicMock()
    app.control.inspect = MagicMock(return_value=MagicMock(
        active=MagicMock(return_value={"worker1": []}),
        reserved=MagicMock(return_value={"worker1": []}),
        stats=MagicMock(return_value={"worker1": {"uptime": 100}}),
    ))
    return app


def mock_celery_task(task_module_path, task_name="mock_task"):
    """Patch a Celery task for testing.

    Args:
        task_module_path: Full path to the task (e.g., 'app.infrastructure.celery_tasks.download_video_task')
        task_name: Name for the mock task

    Returns:
        patch context manager
    """
    mock_task = MagicMock()
    mock_task.apply_async = MagicMock(return_value=MockCeleryTask())
    mock_task.delay = MagicMock(return_value=MockCeleryTask())
    return patch(task_module_path, mock_task)