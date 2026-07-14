from __future__ import annotations

import re
from datetime import timedelta
from typing import Any
from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from .utils import get_thumbnail_urls

logger = get_logger(__name__)


def extract_channel_id_from_input(channel_input: str) -> str | None:
    """Extract a channel ID from various input formats (ID, username, handle, URL)"""
    if not channel_input:
        return None

    if re.match(r"^UC[a-zA-Z0-9_-]{22}$", channel_input):
        return channel_input

    try:
        from urllib.parse import urlparse
        parsed_url = urlparse(channel_input)
        if "youtube.com" in parsed_url.netloc:
            path_parts = parsed_url.path.strip("/").split("/")
            if len(path_parts) >= 2 and path_parts[0] == "channel":
                return path_parts[1]
    except Exception as e:
        logger.debug("Failed to extract channel ID from URL: %s", e)

    return None


def extract_text(data: Any, default: str = "") -> str:
    """Helper to extract text from YouTube data structures"""
    if not data:
        return default

    if isinstance(data, str):
        return data

    if "simpleText" in data:
        return data.get("simpleText", default)

    if "runs" in data:
        return "".join(run.get("text", "") for run in data.get("runs", []))

    if "content" in data:
        return data.get("content", default)

    return default


def extract_from_dynamic_text(dynamic_text: Any, default: str = "") -> str:
    """Extract text from dynamic text view model"""
    if not dynamic_text:
        return default

    if "text" in dynamic_text and "content" in dynamic_text["text"]:
        return dynamic_text["text"]["content"]

    return default


def parse_count(text: Any) -> int:
    """Parse view/subscriber counts with K/M suffixes"""
    if not text or not isinstance(text, str):
        return 0

    match = re.search(r"([\d\.,]+)([MK]?)", text)
    if not match:
        return 0

    num, unit = match.groups()
    count = float(num.replace(",", ""))
    if unit == "M":
        count *= 1000000
    elif unit == "K":
        count *= 1000
    return int(count)


def parse_duration(duration_text: str | None) -> int:
    """
    Parse duration text (e.g. "12:34") into seconds.
    Handles special cases like "Upcoming", "LIVE", "PREMIERING", etc.
    """
    if not duration_text:
        return 0

    special_cases = ["upcoming", "live", "premiering", "premiere", "scheduled"]
    if any(case in duration_text.lower() for case in special_cases):
        return 0

    if "short" in duration_text.lower():
        return 60

    try:
        from .utils import parse_duration_to_seconds
        return parse_duration_to_seconds(duration_text) or 0
    except (ValueError, IndexError):
        return 0


def parse_time_ago(time_text: str | None) -> str | None:
    """Parse relative time (e.g. "3 weeks ago") into an approximate date"""
    if not time_text or "ago" not in time_text.lower():
        return None

    current_time = now_brazil()
    time_text = time_text.lower()

    number_match = re.search(r"(\d+)\s+(\w+)", time_text)
    if not number_match:
        return None

    number = int(number_match.group(1))
    unit = number_match.group(2).rstrip("s")

    time_units: dict[str, timedelta] = {
        "second": timedelta(seconds=number),
        "sec": timedelta(seconds=number),
        "minute": timedelta(minutes=number),
        "min": timedelta(minutes=number),
        "hour": timedelta(hours=number),
        "hr": timedelta(hours=number),
        "day": timedelta(days=number),
        "week": timedelta(weeks=number),
        "wk": timedelta(weeks=number),
        "month": timedelta(days=number * 30),
        "mo": timedelta(days=number * 30),
        "year": timedelta(days=number * 365),
        "yr": timedelta(days=number * 365),
    }

    delta = time_units.get(unit)
    if delta:
        return (current_time - delta).strftime("%Y-%m-%d")
    return None


def extract_video_info(video_renderer: dict[str, Any] | None) -> dict[str, Any] | None:
    """Extract video information from a video renderer object"""
    if not video_renderer:
        return None

    video_id = video_renderer.get("videoId", "")
    if not video_id:
        return None

    video_info: dict[str, Any] = {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "thumbnails": get_thumbnail_urls(video_id),
        "title": extract_text(video_renderer.get("title", {})),
    }

    for overlay in video_renderer.get("thumbnailOverlays", []):
        time_renderer = overlay.get("thumbnailOverlayTimeStatusRenderer", {})
        if time_renderer:
            duration_text = extract_text(time_renderer.get("text", {}))
            if duration_text:
                video_info["duration"] = duration_text
                video_info["duration_seconds"] = parse_duration(duration_text)

        for key in [
            "thumbnailOverlayToggleButtonRenderer",
            "thumbnailOverlayNowPlayingRenderer",
        ]:
            if key in overlay:
                label = overlay.get(key, {}).get("label", "")
                if label:
                    video_info.setdefault("badges", []).append(label)

    published_time = extract_text(video_renderer.get("publishedTimeText", {}))
    if published_time:
        video_info["published_time"] = published_time
        approx_date = parse_time_ago(published_time)
        if approx_date:
            video_info["approximate_upload_date"] = approx_date

    view_count_text = extract_text(video_renderer.get("viewCountText", {}))
    if view_count_text:
        video_info["view_count_text"] = view_count_text
        if "view" in view_count_text.lower():
            if view_count_text.lower().startswith("no "):
                video_info["views"] = 0
            else:
                video_info["views"] = parse_count(view_count_text)

    description = video_renderer.get("descriptionSnippet", {})
    if description:
        video_info["description_snippet"] = extract_text(description)

    for badge in video_renderer.get("badges", []):
        badge_label = badge.get("metadataBadgeRenderer", {}).get("label", "")
        if badge_label:
            video_info.setdefault("badges", []).append(badge_label)

    for badge in video_renderer.get("ownerBadges", []):
        if (
            badge.get("metadataBadgeRenderer", {}).get("style", "")
            == "BADGE_STYLE_TYPE_VERIFIED"
        ):
            video_info["channel_verified"] = True

    return video_info
