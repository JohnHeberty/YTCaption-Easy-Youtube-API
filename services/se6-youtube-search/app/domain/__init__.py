"""
Domain layer for YouTube Search service.

Contains business logic, interfaces, and domain models.
"""

from .interfaces import YouTubeSearchInterface, JobStoreInterface
from .models import VideoInfo, ChannelInfo, PlaylistInfo, Job, SearchRequest, JobListResponse
from .processor import YouTubeSearchProcessor

__all__ = [
    "YouTubeSearchInterface",
    "JobStoreInterface",
    "VideoInfo",
    "ChannelInfo",
    "PlaylistInfo",
    "Job",
    "SearchRequest",
    "JobListResponse",
    "YouTubeSearchProcessor",
]
