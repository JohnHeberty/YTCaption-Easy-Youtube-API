from __future__ import annotations

"""Validators for SE1 Orchestrator."""

import re
from urllib.parse import urlparse


class JobIdValidator:
    """Validate and sanitize job IDs."""

    MAX_LENGTH = 64
    PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

    @classmethod
    def validate(cls, job_id: str | None) -> bool:
        if not job_id or not isinstance(job_id, str):
            return False
        if len(job_id) > cls.MAX_LENGTH:
            return False
        if ".." in job_id or "/" in job_id:
            return False
        return bool(cls.PATTERN.match(job_id))

    @classmethod
    def sanitize(cls, job_id: str | None) -> str | None:
        return job_id if cls.validate(job_id) else None

    @classmethod
    def validate_or_raise(cls, job_id: str) -> str:
        if not cls.validate(job_id):
            raise ValueError(f"Invalid job_id: {job_id!r}")
        return job_id


class URLValidator:
    """Validate HTTP(S) URLs."""

    @classmethod
    def validate(cls, url: str | None) -> bool:
        if not url or not isinstance(url, str):
            return False
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False


class YouTubeURLValidator:
    """Validate YouTube URLs and extract video IDs."""

    PATTERNS = [
        re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})"),
        re.compile(r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})"),
        re.compile(r"youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})"),
    ]

    @classmethod
    def validate(cls, url: str | None) -> bool:
        return cls.extract_video_id(url) is not None

    @classmethod
    def extract_video_id(cls, url: str | None) -> str | None:
        if not url or not isinstance(url, str):
            return None
        for pattern in cls.PATTERNS:
            match = pattern.search(url)
            if match:
                return match.group(1)
        return None
