"""Domain services for Video Downloader.

This module provides domain-level services that orchestrate
business logic operations.
"""

from typing import Optional

from app.core.models import VideoDownloadJob
from common.log_utils import get_logger
from common.job_utils.models import JobStatus
from app.core.validators import ValidationError
from app.domain.interfaces import JobStoreInterface

logger = get_logger(__name__)


class JobService:
    """Service for job-related operations.

    This service encapsulates the business logic for creating,
    updating, and managing download jobs.
    """

    def __init__(self, job_store: JobStoreInterface):
        """Initialize the service.

        Args:
            job_store: Storage implementation for jobs
        """
        self.job_store = job_store

    def create_job(self, url: str, quality: str = "best") -> VideoDownloadJob:
        """Create a new download job.

        Args:
            url: YouTube URL
            quality: Quality preset

        Returns:
            Created job
        """
        job = VideoDownloadJob.create_new(url, quality)
        self.job_store.save_job(job)
        logger.info(f"✅ Job created: {job.id}")
        return job

    def get_or_create_job(self, url: str, quality: str = "best") -> tuple[Job, bool]:
        """Get existing job or create new one.

        Args:
            url: YouTube URL
            quality: Quality preset

        Returns:
            Tuple of (job, is_new)
        """
        # Try to find existing job
        temp_job = VideoDownloadJob.create_new(url, quality)
        existing = self.job_store.get_job(temp_job.id)

        if existing:
            if existing.status == JobStatus.COMPLETED:
                logger.info(f"📋 Returning completed job: {existing.id}")
                return existing, False
            elif existing.status in [JobStatus.QUEUED, "processing"]:
                logger.info(f"⏳ Returning in-progress job: {existing.id}")
                return existing, False
            elif existing.status == JobStatus.FAILED:
                # Retry failed job
                logger.info(f"🔄 Retrying failed job: {existing.id}")
                existing.status = JobStatus.QUEUED
                existing.error_message = None
                existing.progress = 0.0
                self.job_store.update_job(existing)
                return existing, True

        # Create new job
        new_job = self.create_job(url, quality)
        return new_job, True

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job if found, None otherwise

        Raises:
            ValidationError: If job_id is invalid
        """
        try:
            return self.job_store.get_job(job_id)
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting job {job_id}: {e}")
            return None

    def delete_job(self, job_id: str) -> bool:
        """Delete job.

        Args:
            job_id: Job ID

        Returns:
            True if deleted
        """
        try:
            return self.job_store.delete_job(job_id)
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error deleting job {job_id}: {e}")
            return False

    def list_jobs(self, limit: int = 20) -> list[Job]:
        """List recent jobs.

        Args:
            limit: Maximum number of jobs

        Returns:
            List of jobs
        """
        return self.job_store.list_jobs(limit)


class DownloadOrchestrator:
    """Orchestrates the download workflow.

    Coordinates between job management, task submission,
    and download execution.
    """

    def __init__(
        self,
        job_service: JobService,
    ):
        """Initialize the orchestrator.

        Args:
            job_service: Job management service
        """
        self.job_service = job_service

    def process_download_request(
        self,
        url: str,
        quality: str = "best",
    ) -> tuple[Job, bool]:
        """Process a download request.

        Args:
            url: YouTube URL
            quality: Quality preset

        Returns:
            Tuple of (job, is_new)
        """
        job, is_new = self.job_service.get_or_create_job(url, quality)
        return job, is_new
