from __future__ import annotations

from typing import Any
from common.log_utils import get_logger

from .utils import fetch_url, extract_initial_data
from .channel_parsers import extract_channel_id_from_input
from .channel_metadata import extract_channel_metadata
from .channel_videos import extract_channel_videos

logger = get_logger(__name__)

# Re-export for backward compatibility
__all__ = [
    "extract_channel_id_from_input",
    "extract_channel_metadata",
    "extract_channel_videos",
    "get_channel_info",
    "get_channel_videos",
]


def get_channel_info(
    channel_input: str,
    include_videos: bool = True,
    max_videos: int = 10,
    timeout: int = 10,
) -> dict[str, Any]:
    """
    Get detailed information about a YouTube channel with minimal requests.

    Args:
        channel_input: Channel ID, username, handle or URL
        include_videos: Whether to include recent videos
        max_videos: Maximum number of videos to include
        timeout: Request timeout in seconds

    Returns:
        dict: Channel information including metadata and videos
    """
    channel_id = extract_channel_id_from_input(channel_input)

    if channel_id:
        url = f"https://www.youtube.com/channel/{channel_id}"
    elif channel_input.startswith("@"):
        url = f"https://www.youtube.com/{channel_input}"
    elif "/" not in channel_input:
        url = f"https://www.youtube.com/user/{channel_input}"
    else:
        url = channel_input

    html_content = fetch_url(url, timeout=timeout)
    if not html_content:
        return {"error": f"Failed to fetch channel data from {url}"}

    initial_data = extract_initial_data(html_content)
    if not initial_data:
        return {"error": "Failed to extract channel data"}

    if not channel_id:
        channel_id = initial_data.get("header", {}).get(
            "c4TabbedHeaderRenderer", {}
        ).get("channelId") or initial_data.get("metadata", {}).get(
            "channelMetadataRenderer", {}
        ).get(
            "externalId"
        )

    channel_info: dict[str, Any] = {
        "channel_id": channel_id,
        "channel_url": (
            f"https://www.youtube.com/channel/{channel_id}" if channel_id else url
        ),
    }

    metadata = extract_channel_metadata(initial_data)
    if isinstance(metadata, dict):
        channel_info.update(metadata)

    if include_videos:
        videos = extract_channel_videos(initial_data, max_videos)
        if isinstance(videos, list):
            channel_info["videos_count"] = len(videos)
            channel_info["videos"] = videos

    return channel_info


def get_channel_videos(
    channel_input: str,
    max_results: int = 50,
    timeout: int = 10,
) -> dict[str, Any]:
    """
    Get videos from a YouTube channel with minimal requests.

    Args:
        channel_input: Channel ID, username, handle or URL
        max_results: Maximum number of videos to include
        timeout: Request timeout in seconds

    Returns:
        dict: Channel videos information
    """
    channel_info = get_channel_info(
        channel_input, include_videos=True, max_videos=max_results, timeout=timeout
    )

    if "error" in channel_info:
        return channel_info

    return {
        "channel_id": channel_info.get("channel_id", ""),
        "channel_title": channel_info.get("title", ""),
        "videos_count": channel_info.get("videos_count", 0),
        "videos": channel_info.get("videos", []),
    }
