"""Video downloader service implementation.

This module implements the VideoDownloaderInterface with yt-dlp
as the underlying download engine.
"""

import asyncio
import math
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional

import yt_dlp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.constants import (
    CONCURRENT_FRAGMENT_DOWNLOADS,
    EXTRACTOR_RETRIES,
    FILE_ACCESS_RETRIES,
    FRAGMENT_RETRIES,
    MAX_ATTEMPTS_PER_UA,
    MAX_BACKOFF_SECONDS,
    MAX_USER_AGENTS,
    MIN_DISK_SPACE_GB,
    PROGRESS_COMPLETE,
    PROGRESS_INITIAL,
    PROGRESS_MAX_INCOMPLETE,
    PROGRESS_MAX_PRE_DOWNLOAD,
    PROGRESS_POST_DOWNLOAD,
    QUALITY_FORMATS,
)
from app.core.models import VideoDownloadJob
from common.job_utils.models import JobStatus
from app.core.validators import FilenameValidator
from app.domain.interfaces import VideoDownloaderInterface
from app.services.user_agent_manager import UserAgentManager
from common.log_utils import get_logger

logger = get_logger(__name__)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential_jitter(initial=2, max=20),
    retry=retry_if_exception_type((IOError, OSError, ConnectionError)),
    reraise=True,
)
def _extract_video_info(ydl: yt_dlp.YoutubeDL, url: str) -> dict:
    """Extract video metadata with retry for transient network errors.

    Args:
        ydl: YoutubeDL instance
        url: Video URL

    Returns:
        Video metadata dictionary
    """
    return ydl.extract_info(url, download=False)


class YDLPVideoDownloader(VideoDownloaderInterface):
    """Video downloader implementation using yt-dlp.

    This class implements resilient video downloading with:
    - Multiple user agent rotation
    - Exponential backoff retry
    - Progress tracking
    - Disk space validation
    """

    def __init__(
        self,
        cache_dir: str = "./cache",
        ssl_verify: bool = True,
    ):
        """Initialize the downloader.

        Args:
            cache_dir: Directory for downloaded files
            ssl_verify: Whether to verify SSL certificates
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ssl_verify = ssl_verify

        # User agent manager configuration
        quarantine_hours = int(os.getenv("UA_QUARANTINE_HOURS", "48"))
        max_error_count = int(os.getenv("UA_MAX_ERRORS", "3"))

        self.ua_manager = UserAgentManager(
            user_agents_file="user-agents.txt",
            quarantine_hours=quarantine_hours,
            max_error_count=max_error_count,
        )

        # Job store reference (injected)
        self._job_store: Optional[Any] = None

    @property
    def job_store(self) -> Optional[Any]:
        """Get the job store reference."""
        return self._job_store

    @job_store.setter
    def job_store(self, store: Any) -> None:
        """Set the job store reference."""
        self._job_store = store

    def _check_disk_space(self, output_dir: str) -> bool:
        """Check if there's sufficient disk space for download.

        Args:
            output_dir: Directory where file will be saved

        Returns:
            True if sufficient space available
        """
        try:
            stat = shutil.disk_usage(output_dir)
            available_space_gb = stat.free / (1024**3)

            logger.info(f"💾 Disk space available: {available_space_gb:.2f}GB")

            if available_space_gb < MIN_DISK_SPACE_GB:
                logger.error(
                    f"❌ Insufficient disk space! "
                    f"Available: {available_space_gb:.2f}GB, "
                    f"Required: {MIN_DISK_SPACE_GB}GB"
                )
                return False

            return True

        except Exception as e:
            logger.warning(f"⚠️ Could not check disk space: {e}")
            return True  # Fail-open

    def _get_format_selector(self, quality: str) -> str:
        """Get yt-dlp format selector for quality.

        Args:
            quality: Quality preset (best, 720p, audio, etc.)

        Returns:
            yt-dlp format selector string
        """
        return QUALITY_FORMATS.get(quality, QUALITY_FORMATS["best"])

    def _progress_hook(self, d: Dict[str, Any], job: VideoDownloadJob) -> None:
        """Handle download progress updates.

        Args:
            d: Progress data from yt-dlp
            job: Current job being downloaded
        """
        try:
            if d["status"] == "downloading":
                # Calculate progress from bytes
                if "total_bytes" in d and d["total_bytes"]:
                    downloaded = d.get("downloaded_bytes", 0)
                    total = d["total_bytes"]
                    progress = (downloaded / total) * 100
                elif "total_bytes_estimate" in d and d["total_bytes_estimate"]:
                    downloaded = d.get("downloaded_bytes", 0)
                    total = d["total_bytes_estimate"]
                    progress = (downloaded / total) * 100
                else:
                    # Incremental progress if no total size
                    progress = min(job.progress + 1.0, PROGRESS_MAX_INCOMPLETE)

                job.progress = min(progress, PROGRESS_MAX_INCOMPLETE)

                if self._job_store:
                    self._job_store.update_job(job)

            elif d["status"] == "finished":
                job.progress = PROGRESS_COMPLETE
                if self._job_store:
                    self._job_store.update_job(job)

        except Exception as exc:
            logger.warning(f"Error in progress hook: {exc}")

    async def download(self, job: VideoDownloadJob) -> VideoDownloadJob:
        """Download video for the given job.

        Args:
            job: VideoDownloadJob with download parameters

        Returns:
            Updated job with results
        """
        try:
            job.mark_as_processing("Downloading video")

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._sync_download,
                job,
            )

            return result

        except Exception as exc:
            job.mark_as_failed("Download failed")
            job.error_message = str(exc)
            return job

    def _sync_download(self, job: VideoDownloadJob) -> VideoDownloadJob:
        """Synchronous download with retry logic.

        Args:
            job: VideoDownloadJob to download

        Returns:
            Updated job
        """
        # Check disk space first
        if not self._check_disk_space(str(self.cache_dir)):
            job.mark_as_failed("Download failed")
            job.error_message = (
                "Insufficient disk space (minimum 1GB required)"
            )
            if self._job_store:
                self._job_store.update_job(job)
            return job

        total_attempts = MAX_USER_AGENTS * MAX_ATTEMPTS_PER_UA

        logger.info(
            f"🚀 Starting resilient download: "
            f"{MAX_USER_AGENTS} UAs × {MAX_ATTEMPTS_PER_UA} attempts"
        )

        job.progress = PROGRESS_INITIAL
        if self._job_store:
            self._job_store.update_job(job)

        last_error: Optional[Exception] = None
        current_ua: Optional[str] = None

        for ua_index in range(MAX_USER_AGENTS):
            current_ua = self.ua_manager.get_user_agent()
            ua_display = current_ua[:50] if current_ua else "N/A"

            logger.info(
                f"📱 User Agent {ua_index + 1}/{MAX_USER_AGENTS}: {ua_display}"
            )

            for attempt_ua in range(MAX_ATTEMPTS_PER_UA):
                global_attempt = ua_index * MAX_ATTEMPTS_PER_UA + attempt_ua + 1

                logger.info(
                    f"🔄 Attempt {attempt_ua + 1}/{MAX_ATTEMPTS_PER_UA} "
                    f"(global: {global_attempt}/{total_attempts})"
                )

                try:
                    # Calculate backoff delay
                    if global_attempt > 1:
                        delay = min(
                            math.pow(2, 2 + (global_attempt - 2)),
                            MAX_BACKOFF_SECONDS,
                        )
                        logger.warning(
                            f"⏳ Waiting {delay:.0f}s (exponential backoff)..."
                        )
                        time.sleep(delay)

                    # Update job with current UA
                    job.current_user_agent = current_ua

                    # Update progress
                    progress_base = PROGRESS_INITIAL + (
                        (PROGRESS_MAX_PRE_DOWNLOAD - PROGRESS_INITIAL)
                        * global_attempt
                        / total_attempts
                    )
                    job.progress = min(progress_base, PROGRESS_MAX_PRE_DOWNLOAD)
                    if self._job_store:
                        self._job_store.update_job(job)

                    # Get yt-dlp options
                    opts = self._get_ydl_opts(job, current_ua)

                    with yt_dlp.YoutubeDL(opts) as ydl:
                        logger.info(
                            f"📥 Extracting video info (attempt {global_attempt})..."
                        )
                        info = _extract_video_info(ydl, job.url)

                        # Progress after info extraction
                        job.progress = PROGRESS_POST_DOWNLOAD
                        if self._job_store:
                            self._job_store.update_job(job)

                        # Update job with video info
                        title = info.get("title", "unknown")
                        ext = info.get("ext", "mp4")

                        filename = f"{job.id}.{ext}"
                        job.filename = filename
                        job.file_path = str(self.cache_dir / filename)

                        logger.info(f"⬇️ Starting download: {filename}")

                        # Download video
                        ydl.download([job.url])

                        # Verify file was created
                        downloaded_files = list(self.cache_dir.glob(f"{job.id}.*"))
                        if downloaded_files:
                            actual_file = downloaded_files[0]
                            job.file_path = str(actual_file)
                            job.filename = actual_file.name
                            job.file_size = actual_file.stat().st_size

                            job.mark_as_completed()
                            job.progress = PROGRESS_COMPLETE

                            logger.info(
                                f"✅ Download SUCCESS after {global_attempt} attempts: "
                                f"{job.filename} ({job.file_size} bytes)"
                            )

                            return job
                        else:
                            raise FileNotFoundError(
                                "File not found after download"
                            )

                except Exception as exc:
                    last_error = exc
                    error_msg = str(exc)

                    logger.error(
                        f"❌ Error in attempt {global_attempt}: {error_msg}"
                    )

                    if attempt_ua < MAX_ATTEMPTS_PER_UA - 1:
                        continue
                    else:
                        # Last attempt with this UA - quarantine it
                        error_details = (
                            f"Failed after {MAX_ATTEMPTS_PER_UA} attempts: "
                            f"{error_msg}"
                        )
                        self.ua_manager.report_error(current_ua, error_details)
                        logger.warning(
                            f"🚫 UA quarantined after {MAX_ATTEMPTS_PER_UA} failures"
                        )
                        break

        # All attempts failed
        logger.error(
            f"💥 Total failure after {total_attempts} attempts with "
            f"{MAX_USER_AGENTS} user agents"
        )

        job.mark_as_failed("Download failed")
        job.error_message = (
            f"Download failed after {total_attempts} attempts. "
            f"Last error: {last_error}"
        )

        if current_ua:
            self.ua_manager.report_error(
                current_ua, f"Final failure: {last_error}"
            )

        return job

    def _get_ydl_opts(self, job: VideoDownloadJob, user_agent: str) -> Dict[str, Any]:
        """Build yt-dlp options.

        Args:
            job: Current job
            user_agent: User agent string

        Returns:
            yt-dlp options dictionary
        """
        filename_template = f"{job.id}.%(ext)s"

        opts = {
            "outtmpl": str(self.cache_dir / filename_template),
            "format": self._get_format_selector(job.quality),
            "noplaylist": True,
            "extractaudio": False,
            "writeinfojson": False,
            "writedescription": False,
            "writesubtitles": False,
            "writeautomaticsub": False,
            "ignoreerrors": False,
            "progress_hooks": [lambda d: self._progress_hook(d, job)],
            "http_headers": {"User-Agent": user_agent},
            # Fragment handling
            "fragment_retries": FRAGMENT_RETRIES,
            "skip_unavailable_fragments": False,
            "extractor_retries": EXTRACTOR_RETRIES,
            "file_access_retries": FILE_ACCESS_RETRIES,
            "concurrent_fragment_downloads": CONCURRENT_FRAGMENT_DOWNLOADS,
            # Livestream options
            "live_from_start": False,
            "wait_for_video": 0,
            # SSL verification
            "verify": self.ssl_verify,
        }

        return opts

    def get_file_path(self, job: VideoDownloadJob) -> Optional[Path]:
        """Get file path for a completed job.

        Args:
            job: VideoDownloadJob to get file path for

        Returns:
            Path if file exists, None otherwise
        """
        if job.file_path:
            path = Path(job.file_path)
            if path.exists():
                return path
        return None

    def get_user_agent_stats(self) -> Dict[str, Any]:
        """Get user agent statistics.

        Returns:
            Statistics dictionary
        """
        return self.ua_manager.get_stats()

    def reset_user_agent(self, user_agent: str) -> bool:
        """Reset a quarantined user agent.

        Args:
            user_agent: User agent to reset

        Returns:
            True if successful
        """
        return self.ua_manager.reset_user_agent(user_agent)
