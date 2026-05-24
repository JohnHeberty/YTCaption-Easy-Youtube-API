"""Domain layer for Video Downloader Service.

This package contains domain models, interfaces, and business logic
that is independent of external frameworks and implementations.
"""

from .interfaces import (
    VideoDownloaderInterface,
    JobStoreInterface,
    CeleryTaskInterface,
    UserAgentManagerInterface,
)

__all__ = [
    "VideoDownloaderInterface",
    "JobStoreInterface",
    "CeleryTaskInterface",
    "UserAgentManagerInterface",
]
