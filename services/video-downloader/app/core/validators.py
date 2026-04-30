"""Core validators for Video Downloader Service.

This module provides validation classes for various inputs to ensure
security and data integrity.
"""

import re
from typing import Optional
from urllib.parse import urlparse


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class JobIdValidator:
    """Validator for job IDs used in Redis keys.

    Prevents path traversal and injection attacks by validating
    that job IDs only contain safe characters.

    Pattern allows:
    - Alphanumeric characters (a-z, A-Z, 0-9)
    - Underscores (_)
    - Hyphens (-)
    - Length: 1-64 characters
    """

    PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')
    MAX_LENGTH = 64

    @classmethod
    def validate(cls, job_id: str) -> bool:
        """Validate job_id format.

        Args:
            job_id: The job ID to validate

        Returns:
            True if valid, False otherwise
        """
        if not job_id or not isinstance(job_id, str):
            return False
        return bool(cls.PATTERN.match(job_id))

    @classmethod
    def validate_or_raise(cls, job_id: str) -> str:
        """Validate job_id and return it, or raise ValidationError.

        Args:
            job_id: The job ID to validate

        Returns:
            The validated job_id

        Raises:
            ValidationError: If job_id is invalid
        """
        if not cls.validate(job_id):
            raise ValidationError(
                f"Invalid job_id: {job_id}. Must match pattern: {cls.PATTERN.pattern}"
            )
        return job_id

    @classmethod
    def sanitize(cls, job_id: str) -> Optional[str]:
        """Sanitize job_id by truncating if too long.

        Args:
            job_id: The job ID to sanitize

        Returns:
            Sanitized job_id or None if invalid
        """
        if not isinstance(job_id, str) or not job_id:
            return None
        # Truncate to max length and validate
        truncated = job_id[:cls.MAX_LENGTH]
        if not cls.PATTERN.match(truncated):
            return None
        return truncated


class URLValidator:
    """Validator for YouTube URLs.

    Validates URLs to ensure they are valid YouTube URLs
    and prevents potential security issues.
    """

    MAX_URL_LENGTH = 2000
    YOUTUBE_PATTERNS = [
        re.compile(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$'),
        re.compile(r'^(https?://)?(m\.)?(youtube\.com|youtu\.be)/.+$'),
    ]
    VIDEO_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{11}$')

    @classmethod
    def is_valid_youtube_url(cls, url: str) -> bool:
        """Check if URL is a valid YouTube URL.

        Args:
            url: The URL to validate

        Returns:
            True if valid YouTube URL, False otherwise
        """
        if not url or len(url) > cls.MAX_URL_LENGTH:
            return False

        try:
            result = urlparse(url)
            if not all([result.scheme in ('http', 'https'), result.netloc]):
                return False
        except Exception:
            return False

        return any(pattern.match(url) for pattern in cls.YOUTUBE_PATTERNS)

    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL.

        Args:
            url: The YouTube URL

        Returns:
            Video ID if found, None otherwise
        """
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                if cls.VIDEO_ID_PATTERN.match(video_id):
                    return video_id

        return None

    @classmethod
    def validate_or_raise(cls, url: str) -> str:
        """Validate URL and return it, or raise ValidationError.

        Args:
            url: The URL to validate

        Returns:
            The validated URL

        Raises:
            ValidationError: If URL is invalid
        """
        if not cls.is_valid_youtube_url(url):
            raise ValidationError(f"Invalid YouTube URL: {url}")
        return url


class FilenameValidator:
    """Validator for filenames.

    Ensures filenames are safe and don't contain path traversal
    or other dangerous characters.
    """

    ALLOWED_EXTENSIONS = {'.mp4', '.webm', '.mkv', '.mp3', '.m4a', '.wav', '.opus'}
    INVALID_CHARS = '<>:"/\\|?*\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f'
    MAX_FILENAME_LENGTH = 200

    @classmethod
    def sanitize(cls, filename: str) -> str:
        """Sanitize filename by removing invalid characters.

        Args:
            filename: The filename to sanitize

        Returns:
            Sanitized filename
        """
        sanitized = filename
        for char in cls.INVALID_CHARS:
            sanitized = sanitized.replace(char, '_')
        return sanitized[:cls.MAX_FILENAME_LENGTH]

    @classmethod
    def is_valid_extension(cls, filename: str) -> bool:
        """Check if file has an allowed extension.

        Args:
            filename: The filename to check

        Returns:
            True if extension is allowed, False otherwise
        """
        from pathlib import Path
        ext = Path(filename).suffix.lower()
        return ext in cls.ALLOWED_EXTENSIONS

    @classmethod
    def validate(cls, filename: str) -> bool:
        """Validate filename is safe.

        Args:
            filename: The filename to validate

        Returns:
            True if valid, False otherwise
        """
        if not filename or len(filename) > cls.MAX_FILENAME_LENGTH:
            return False

        # Check for path traversal attempts
        if '..' in filename or filename.startswith('/'):
            return False

        # Check for invalid characters
        if any(c in filename for c in cls.INVALID_CHARS):
            return False

        return True
