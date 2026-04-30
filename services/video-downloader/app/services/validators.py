"""Service-level validators for Video Downloader Service.

This module provides validation classes for service-level operations
such as file uploads, downloads, and job processing.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from common.log_utils import get_logger
from app.core.constants import MAX_FILE_SIZE_BYTES, MIN_DISK_SPACE_GB
from app.core.models import VideoDownloadJob as Job
from app.core.validators import (
    FilenameValidator,
    JobIdValidator,
    URLValidator,
    ValidationError,
)

logger = get_logger(__name__)


class VideoValidationResult:
    """Result of video validation."""

    def __init__(
        self,
        is_valid: bool,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.is_valid = is_valid
        self.error_message = error_message
        self.metadata = metadata or {}

    def __bool__(self) -> bool:
        return self.is_valid


class JobValidator:
    """Validator for job operations."""

    @staticmethod
    def validate_job_id(job_id: str) -> bool:
        """Validate job ID format.

        Args:
            job_id: Job ID to validate

        Returns:
            True if valid
        """
        return JobIdValidator.validate(job_id)

    @staticmethod
    def validate_job_exists(job: Optional[Job]) -> Tuple[bool, Optional[str]]:
        """Validate job exists.

        Args:
            job: Job to check

        Returns:
            Tuple of (is_valid, error_message)
        """
        if job is None:
            return False, "Job not found"
        return True, None

    @staticmethod
    def validate_job_not_expired(job: Job) -> Tuple[bool, Optional[str]]:
        """Validate job has not expired.

        Args:
            job: Job to check

        Returns:
            Tuple of (is_valid, error_message)
        """
        if job.is_expired:
            return False, "Job has expired"
        return True, None

    @staticmethod
    def validate_job_completed(job: Job) -> Tuple[bool, Optional[str]]:
        """Validate job is completed.

        Args:
            job: Job to check

        Returns:
            Tuple of (is_valid, error_message)
        """
        from common.job_utils.models import JobStatus

        if job.status != JobStatus.COMPLETED:
            return False, f"Job not completed. Status: {job.status.value}"
        return True, None


class VideoValidator:
    """Validator for video-related operations."""

    @classmethod
    def validate_url(cls, url: str) -> VideoValidationResult:
        """Validate YouTube URL.

        Args:
            url: URL to validate

        Returns:
            Validation result
        """
        if not URLValidator.is_valid_youtube_url(url):
            return VideoValidationResult(
                is_valid=False,
                error_message=f"Invalid YouTube URL: {url}",
            )

        video_id = URLValidator.extract_video_id(url)
        if not video_id:
            return VideoValidationResult(
                is_valid=False,
                error_message="Could not extract video ID from URL",
            )

        return VideoValidationResult(
            is_valid=True,
            metadata={"video_id": video_id},
        )

    @classmethod
    def validate_file(cls, file_path: Path) -> VideoValidationResult:
        """Validate downloaded file.

        Args:
            file_path: Path to file

        Returns:
            Validation result
        """
        if not file_path.exists():
            return VideoValidationResult(
                is_valid=False,
                error_message=f"File not found: {file_path}",
            )

        if not file_path.is_file():
            return VideoValidationResult(
                is_valid=False,
                error_message=f"Path is not a file: {file_path}",
            )

        file_size = file_path.stat().st_size
        if file_size == 0:
            return VideoValidationResult(
                is_valid=False,
                error_message="File is empty",
            )

        if file_size > MAX_FILE_SIZE_BYTES:
            return VideoValidationResult(
                is_valid=False,
                error_message=(
                    f"File too large: {file_size} bytes "
                    f"(max: {MAX_FILE_SIZE_BYTES} bytes)"
                ),
            )

        return VideoValidationResult(
            is_valid=True,
            metadata={
                "file_size": file_size,
                "filename": file_path.name,
            },
        )

    @classmethod
    def validate_filename(cls, filename: str) -> VideoValidationResult:
        """Validate filename.

        Args:
            filename: Filename to validate

        Returns:
            Validation result
        """
        if not FilenameValidator.validate(filename):
            return VideoValidationResult(
                is_valid=False,
                error_message=f"Invalid filename: {filename}",
            )

        return VideoValidationResult(is_valid=True)


class SystemValidator:
    """Validator for system resources."""

    @staticmethod
    def check_disk_space(path: Path, min_gb: float = MIN_DISK_SPACE_GB) -> Tuple[bool, float]:
        """Check available disk space.

        Args:
            path: Path to check
            min_gb: Minimum required space in GB

        Returns:
            Tuple of (has_space, available_gb)
        """
        import shutil

        try:
            stat = shutil.disk_usage(path)
            available_gb = stat.free / (1024**3)
            return available_gb >= min_gb, available_gb
        except Exception as e:
            logger.warning(f"Could not check disk space: {e}")
            return True, 0.0  # Fail-open


class CeleryValidator:
    """Validator for Celery operations."""

    @staticmethod
    def validate_workers(celery_app) -> Tuple[bool, Optional[str]]:
        """Validate Celery workers are available.

        Args:
            celery_app: Celery application instance

        Returns:
            Tuple of (is_valid, error_message)
        """
        from app.core.constants import CELERY_INSPECT_TIMEOUT

        try:
            inspect = celery_app.control.inspect(timeout=CELERY_INSPECT_TIMEOUT)
            active_workers = inspect.active()

            if not active_workers:
                return False, "No Celery workers available"

            return True, None

        except Exception as e:
            logger.warning(f"Could not check Celery workers: {e}")
            return True, None  # Fail-open


# Export all validators
__all__ = [
    "VideoValidationResult",
    "JobValidator",
    "VideoValidator",
    "SystemValidator",
    "CeleryValidator",
    "ValidationError",
]
