"""Tests for Video Downloader service.

These tests verify the YDLPVideoDownloader implementation.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import yt_dlp

from app.core.models import VideoDownloadJob as Job, JobStatus
from app.services.video_downloader import YDLPVideoDownloader


class TestYDLPVideoDownloader:
    """Test cases for YDLPVideoDownloader."""

    @pytest.fixture
    def downloader(self, tmp_path):
        """Create a test downloader instance."""
        return YDLPVideoDownloader(cache_dir=str(tmp_path), ssl_verify=False)

    @pytest.fixture
    def sample_job(self):
        """Create a sample job."""
        return Job.create_new("https://www.youtube.com/watch?v=test123", "best")

    def test_init_creates_cache_dir(self, tmp_path):
        """Test that initialization creates cache directory."""
        cache_dir = tmp_path / "test_cache"
        downloader = YDLPVideoDownloader(cache_dir=str(cache_dir))
        assert cache_dir.exists()

    def test_check_disk_space_passes(self, downloader):
        """Test disk space check passes when space available."""
        with patch("shutil.disk_usage") as mock_disk_usage:
            # Mock 10GB available
            mock_disk_usage.return_value = MagicMock(free=10 * 1024**3)
            result = downloader._check_disk_space("/tmp")
            assert result is True

    def test_check_disk_space_fails(self, downloader):
        """Test disk space check fails when insufficient space."""
        with patch("shutil.disk_usage") as mock_disk_usage:
            # Mock 500MB available (less than 1GB minimum)
            mock_disk_usage.return_value = MagicMock(free=500 * 1024**2)
            result = downloader._check_disk_space("/tmp")
            assert result is False

    def test_get_format_selector_best(self, downloader):
        """Test getting format selector for best quality."""
        result = downloader._get_format_selector("best")
        assert "bv*" in result
        assert "ext=mp4" in result

    def test_get_format_selector_audio(self, downloader):
        """Test getting format selector for audio."""
        result = downloader._get_format_selector("audio")
        assert "bestaudio" in result

    def test_get_ydl_opts_structure(self, downloader, sample_job):
        """Test yt-dlp options structure."""
        opts = downloader._get_ydl_opts(sample_job, "test-user-agent")

        assert "outtmpl" in opts
        assert "format" in opts
        assert "http_headers" in opts
        assert opts["http_headers"]["User-Agent"] == "test-user-agent"
        assert opts["noplaylist"] is True
        assert opts["verify"] is False

    def test_job_store_property(self, downloader):
        """Test job store property."""
        mock_store = MagicMock()
        downloader.job_store = mock_store
        assert downloader.job_store == mock_store

    def test_get_file_path_none(self, downloader, sample_job):
        """Test getting file path when no file."""
        result = downloader.get_file_path(sample_job)
        assert result is None

    def test_get_file_path_exists(self, downloader, sample_job, tmp_path):
        """Test getting file path when file exists."""
        # Create a test file
        test_file = tmp_path / f"{sample_job.id}.mp4"
        test_file.write_text("test content")
        sample_job.file_path = str(test_file)

        result = downloader.get_file_path(sample_job)
        assert result == test_file

    def test_get_user_agent_stats(self, downloader):
        """Test getting user agent stats."""
        stats = downloader.get_user_agent_stats()
        assert isinstance(stats, dict)

    def test_reset_user_agent(self, downloader):
        """Test resetting user agent."""
        # Just verify it doesn't raise
        result = downloader.reset_user_agent("test-ua")
        assert isinstance(result, bool)


class TestVideoDownloaderEdgeCases:
    """Test edge cases for Video Downloader."""

    def test_progress_hook_downloading_with_total(self):
        """Test progress hook with total bytes."""
        downloader = YDLPVideoDownloader(cache_dir="/tmp")
        job = Job.create_new("https://youtube.com/watch?v=test", "best")

        d = {
            "status": "downloading",
            "total_bytes": 1000,
            "downloaded_bytes": 500,
        }

        downloader._progress_hook(d, job)
        assert job.progress == 50.0

    def test_progress_hook_downloading_with_estimate(self):
        """Test progress hook with estimated total."""
        downloader = YDLPVideoDownloader(cache_dir="/tmp")
        job = Job.create_new("https://youtube.com/watch?v=test", "best")

        d = {
            "status": "downloading",
            "total_bytes_estimate": 1000,
            "downloaded_bytes": 250,
        }

        downloader._progress_hook(d, job)
        assert job.progress == 25.0

    def test_progress_hook_finished(self):
        """Test progress hook when download finished."""
        downloader = YDLPVideoDownloader(cache_dir="/tmp")
        job = Job.create_new("https://youtube.com/watch?v=test", "best")

        d = {"status": "finished"}

        downloader._progress_hook(d, job)
        assert job.progress == 100.0

    def test_progress_hook_exception_handled(self):
        """Test progress hook handles exceptions gracefully."""
        downloader = YDLPVideoDownloader(cache_dir="/tmp")
        job = Job.create_new("https://youtube.com/watch?v=test", "best")

        # Malformed data should not raise
        d = {"status": "downloading"}  # Missing total_bytes
        downloader._progress_hook(d, job)  # Should not raise
