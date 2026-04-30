"""Tests for service validators.

These tests verify the service-level validation logic.
"""

import pytest
from datetime import datetime, timedelta

from app.core.models import VideoDownloadJob as Job, JobStatus
from app.services.validators import (
    CeleryValidator,
    JobValidator,
    SystemValidator,
    VideoValidationResult,
    VideoValidator,
)


class TestJobValidator:
    """Test cases for JobValidator."""

    def test_validate_job_id_valid(self):
        """Test validating valid job ID."""
        result = JobValidator.validate_job_id("valid_job_123")
        assert result is True

    def test_validate_job_id_invalid(self):
        """Test validating invalid job ID."""
        result = JobValidator.validate_job_id("invalid job!")
        assert result is False

    def test_validate_job_exists_found(self):
        """Test validating existing job."""
        job = Job.create_new("https://youtube.com/watch?v=test", "best")
        is_valid, error = JobValidator.validate_job_exists(job)
        assert is_valid is True
        assert error is None

    def test_validate_job_exists_not_found(self):
        """Test validating non-existent job."""
        is_valid, error = JobValidator.validate_job_exists(None)
        assert is_valid is False
        assert error == "Job not found"

    def test_validate_job_not_expired(self):
        """Test validating non-expired job."""
        job = Job.create_new("https://youtube.com/watch?v=test", "best")
        # Job is not expired by default (expires in 24h)
        is_valid, error = JobValidator.validate_job_not_expired(job)
        assert is_valid is True

    def test_validate_job_expired(self):
        """Test validating expired job."""
        from common.datetime_utils import now_brazil
        job = Job.create_new("https://youtube.com/watch?v=test", "best")
        # Manually expire the job
        job.expires_at = now_brazil() - timedelta(hours=1)
        is_valid, error = JobValidator.validate_job_not_expired(job)
        assert is_valid is False
        assert error == "Job has expired"

    def test_validate_job_completed_success(self):
        """Test validating completed job."""
        job = Job.create_new("https://youtube.com/watch?v=test", "best")
        job.status = JobStatus.COMPLETED
        is_valid, error = JobValidator.validate_job_completed(job)
        assert is_valid is True

    def test_validate_job_completed_failure(self):
        """Test validating incomplete job."""
        job = Job.create_new("https://youtube.com/watch?v=test", "best")
        job.status = JobStatus.DOWNLOADING
        is_valid, error = JobValidator.validate_job_completed(job)
        assert is_valid is False
        assert "not completed" in error


class TestVideoValidator:
    """Test cases for VideoValidator."""

    def test_validate_url_valid(self):
        """Test validating valid YouTube URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = VideoValidator.validate_url(url)
        assert isinstance(result, VideoValidationResult)
        assert result.is_valid is True
        assert result.metadata.get("video_id") == "dQw4w9WgXcQ"

    def test_validate_url_invalid(self):
        """Test validating invalid URL."""
        result = VideoValidator.validate_url("not_a_valid_url")
        assert result.is_valid is False
        assert result.error_message is not None

    def test_validate_filename_valid(self):
        """Test validating valid filename."""
        result = VideoValidator.validate_filename("video.mp4")
        assert result.is_valid is True

    def test_validate_filename_invalid(self):
        """Test validating invalid filename."""
        result = VideoValidator.validate_filename("../etc/passwd")
        assert result.is_valid is False


class TestSystemValidator:
    """Test cases for SystemValidator."""

    def test_check_disk_space(self, tmp_path):
        """Test checking disk space."""
        has_space, available_gb = SystemValidator.check_disk_space(
            tmp_path, min_gb=0.001  # Very low requirement
        )
        assert has_space is True
        assert available_gb > 0


class TestCeleryValidator:
    """Test cases for CeleryValidator."""

    def test_validate_workers_mock(self, monkeypatch):
        """Test validating Celery workers with mock."""
        # Create a mock Celery app
        class MockInspect:
            def active(self):
                return {"worker1": []}

        class MockCelery:
            def control(self):
                return self

            def inspect(self, timeout=None):
                return MockInspect()

        celery_app = MockCelery()
        is_valid, error = CeleryValidator.validate_workers(celery_app)
        assert is_valid is True
        assert error is None

    def test_validate_workers_no_workers(self, monkeypatch):
        """Test validating when no workers available."""
        import types

        class MockInspect:
            def active(self):
                return None  # No workers

        class MockControl:
            def inspect(self, timeout=None):
                return MockInspect()

        # Create a proper mock that behaves like Celery's control
        mock_control = MockControl()
        mock_celery = types.SimpleNamespace()
        mock_celery.control = mock_control  # Not a function, but the control object

        is_valid, error = CeleryValidator.validate_workers(mock_celery)
        assert is_valid is False
        assert error == "No Celery workers available"

    def test_validate_workers_exception(self, monkeypatch):
        """Test validating when exception occurs (fail-open)."""
        class MockCelery:
            def control(self):
                raise Exception("Connection error")

        celery_app = MockCelery()
        is_valid, error = CeleryValidator.validate_workers(celery_app)
        # Fail-open: returns True on exception
        assert is_valid is True
