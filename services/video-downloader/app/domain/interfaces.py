"""Domain interfaces for Video Downloader Service.

This module defines the abstract interfaces used throughout the service,
following the Dependency Inversion Principle (DIP) from SOLID.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any

from app.core import models

VideoDownloadJob = models.VideoDownloadJob
Job = VideoDownloadJob  # alias for compatibility


class VideoDownloaderInterface(ABC):
    """Abstract interface for video downloaders.

    This interface allows for different implementations of video downloading
    strategies without changing the core business logic.
    """

    @abstractmethod
    async def download(self, job: VideoDownloadJob) -> VideoDownloadJob:
        """Download video for the given job.

        Args:
            job: The job containing download parameters

        Returns:
            Updated job with download results
        """
        pass

    @abstractmethod
    def get_file_path(self, job: VideoDownloadJob) -> Optional[Path]:
        """Get the file path for a completed job.

        Args:
            job: The job to get file path for

        Returns:
            Path to the downloaded file, or None if not found
        """
        pass

    @abstractmethod
    def _check_disk_space(self, output_dir: str) -> bool:
        """Check if there's sufficient disk space for download.

        Args:
            output_dir: Directory where file will be saved

        Returns:
            True if sufficient space available, False otherwise
        """
        pass


class JobStoreInterface(ABC):
    """Abstract interface for job storage.

    This interface abstracts the job storage mechanism, allowing
    different implementations (Redis, database, memory, etc.).
    """

    @abstractmethod
    def save_job(self, job: VideoDownloadJob) -> VideoDownloadJob:
        """Save a job to storage.

        Args:
            job: The job to save

        Returns:
            The saved job
        """
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> Optional[VideoDownloadJob]:
        """Retrieve a job by ID.

        Args:
            job_id: The job ID

        Returns:
            The job if found, None otherwise
        """
        pass

    @abstractmethod
    def update_job(self, job: VideoDownloadJob) -> VideoDownloadJob:
        """Update an existing job.

        Args:
            job: The job to update

        Returns:
            The updated job
        """
        pass

    @abstractmethod
    def delete_job(self, job_id: str) -> bool:
        """Delete a job from storage.

        Args:
            job_id: The job ID to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def list_jobs(self, limit: int = 100) -> list[VideoDownloadJob]:
        """List jobs from storage.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of jobs
        """
        pass


class CeleryTaskInterface(ABC):
    """Abstract interface for Celery task submission.

    This interface abstracts the task queue mechanism.
    """

    @abstractmethod
    def submit_task(self, job: VideoDownloadJob) -> str:
        """Submit a job as a Celery task.

        Args:
            job: The job to submit

        Returns:
            Task ID from Celery
        """
        pass

    @abstractmethod
    def check_workers(self) -> Dict[str, Any]:
        """Check status of Celery workers.

        Returns:
            Dictionary with worker status information
        """
        pass


class UserAgentManagerInterface(ABC):
    """Abstract interface for user agent management.

    This interface abstracts user agent rotation and error tracking.
    """

    @abstractmethod
    def get_user_agent(self) -> Optional[str]:
        """Get next available user agent.

        Returns:
            User agent string, or None if none available
        """
        pass

    @abstractmethod
    def report_error(self, user_agent: str, error: str) -> None:
        """Report an error for a user agent.

        Args:
            user_agent: The user agent that caused the error
            error: Error message
        """
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get user agent statistics.

        Returns:
            Dictionary with user agent statistics
        """
        pass
