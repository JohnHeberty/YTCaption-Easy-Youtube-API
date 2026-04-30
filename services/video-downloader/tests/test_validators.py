"""Tests for core validators.

These tests verify the validation logic for job IDs, URLs, and filenames.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.core.validators import (
    FilenameValidator,
    JobIdValidator,
    URLValidator,
    ValidationError,
)


class TestJobIdValidator:
    """Test cases for JobIdValidator."""

    @pytest.mark.parametrize(
        "job_id,expected",
        [
            # Valid cases
            ("abc123", True),
            ("ABC123", True),
            ("abc-123", True),
            ("abc_123", True),
            ("abc123_", True),
            ("a", True),  # Min length
            ("a" * 64, True),  # Max length
            # Invalid cases
            ("", False),  # Empty
            ("abc 123", False),  # Space
            ("abc.123", False),  # Dot
            ("abc/123", False),  # Slash
            ("abc\\123", False),  # Backslash
            ("a" * 65, False),  # Too long
            ("abc@123", False),  # Special char
            ("abc:123", False),  # Colon
            (None, False),  # None
            (123, False),  # Not string
        ],
    )
    def test_validate(self, job_id, expected):
        """Test job ID validation."""
        result = JobIdValidator.validate(job_id)
        assert result == expected

    def test_validate_or_raise_valid(self):
        """Test validate_or_raise with valid ID."""
        result = JobIdValidator.validate_or_raise("valid_job_123")
        assert result == "valid_job_123"

    def test_validate_or_raise_invalid(self):
        """Test validate_or_raise with invalid ID raises exception."""
        with pytest.raises(ValidationError) as exc_info:
            JobIdValidator.validate_or_raise("invalid job!")
        assert "Invalid job_id" in str(exc_info.value)

    def test_sanitize_valid(self):
        """Test sanitize with valid ID."""
        result = JobIdValidator.sanitize("valid_job_123")
        assert result == "valid_job_123"

    def test_sanitize_invalid(self):
        """Test sanitize with invalid ID returns None."""
        result = JobIdValidator.sanitize("invalid job!")
        assert result is None

    def test_sanitize_truncates_long_id(self):
        """Test sanitize truncates long IDs."""
        # 100 'a's should be truncated to 64 valid chars
        long_id = "a" * 100
        result = JobIdValidator.sanitize(long_id)
        assert result is not None
        assert len(result) == 64


class TestURLValidator:
    """Test cases for URLValidator."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            # Valid YouTube URLs
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
            ("https://youtube.com/watch?v=dQw4w9WgXcQ", True),
            ("https://youtu.be/dQw4w9WgXcQ", True),
            ("http://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
            ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", True),
            # Invalid URLs
            ("", False),  # Empty
            ("not_a_url", False),
            ("ftp://youtube.com/watch?v=test", False),  # Wrong scheme
            ("https://example.com/video", False),  # Not YouTube
            ("a" * 2001, False),  # Too long
        ],
    )
    def test_is_valid_youtube_url(self, url, expected):
        """Test YouTube URL validation."""
        result = URLValidator.is_valid_youtube_url(url)
        assert result == expected

    def test_extract_video_id_standard_url(self):
        """Test video ID extraction from standard URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = URLValidator.extract_video_id(url)
        assert result == "dQw4w9WgXcQ"

    def test_extract_video_id_short_url(self):
        """Test video ID extraction from short URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        result = URLValidator.extract_video_id(url)
        assert result == "dQw4w9WgXcQ"

    def test_extract_video_id_embed_url(self):
        """Test video ID extraction from embed URL."""
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        result = URLValidator.extract_video_id(url)
        assert result == "dQw4w9WgXcQ"

    def test_extract_video_id_invalid(self):
        """Test video ID extraction from invalid URL."""
        url = "https://example.com/video"
        result = URLValidator.extract_video_id(url)
        assert result is None

    def test_validate_or_raise_valid(self):
        """Test validate_or_raise with valid URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = URLValidator.validate_or_raise(url)
        assert result == url

    def test_validate_or_raise_invalid(self):
        """Test validate_or_raise with invalid URL raises exception."""
        with pytest.raises(ValidationError) as exc_info:
            URLValidator.validate_or_raise("not_a_youtube_url")
        assert "Invalid YouTube URL" in str(exc_info.value)


class TestFilenameValidator:
    """Test cases for FilenameValidator."""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            # Valid filenames
            ("video.mp4", True),
            ("my_video.webm", True),
            ("audio.mp3", True),
            ("test-file.mkv", True),
            # Invalid filenames
            ("../etc/passwd", False),  # Path traversal
            ("/etc/passwd", False),  # Absolute path
            ("video\x00.exe", False),  # Null byte
            ("video<>test.mp4", False),  # Invalid chars
            ("", False),  # Empty
            ("a" * 201, False),  # Too long
        ],
    )
    def test_validate(self, filename, expected):
        """Test filename validation."""
        result = FilenameValidator.validate(filename)
        assert result == expected

    @pytest.mark.parametrize(
        "filename,expected_ext",
        [
            ("video.mp4", True),
            ("video.MP4", True),  # Case insensitive
            ("video.webm", True),
            ("video.mkv", True),
            ("video.mp3", True),
            ("video.exe", False),  # Not allowed
            ("video", False),  # No extension
        ],
    )
    def test_is_valid_extension(self, filename, expected_ext):
        """Test extension validation."""
        result = FilenameValidator.is_valid_extension(filename)
        assert result == expected_ext

    def test_sanitize_removes_invalid_chars(self):
        """Test sanitize removes invalid characters."""
        result = FilenameValidator.sanitize("video<>test.mp4")
        assert result == "video__test.mp4"

    def test_sanitize_truncates_long_filename(self):
        """Test sanitize truncates long filenames."""
        long_name = "a" * 250 + ".mp4"
        result = FilenameValidator.sanitize(long_name)
        assert len(result) == 200
