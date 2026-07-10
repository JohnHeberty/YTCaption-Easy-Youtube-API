from __future__ import annotations

from typing import Any
from common.log_utils import get_logger

from .channel_parsers import extract_video_info

logger = get_logger(__name__)


def extract_channel_videos(
    initial_data: dict[str, Any], max_videos: int = 10
) -> list[dict[str, Any]]:
    """
    Extract recent videos from the channel with detailed information.

    Uses multiple extraction strategies to support different YouTube structures:
    1. Try Videos tab first (richGridRenderer or gridRenderer)
    2. If Videos tab is empty, try Home tab (sectionListRenderer with videoRenderer)
    3. Try shelfRenderer in Home tab as fallback
    4. secondaryContents as last resort
    """
    videos: list[dict[str, Any]] = []

    try:
        tabs = (
            initial_data.get("contents", {})
            .get("twoColumnBrowseResultsRenderer", {})
            .get("tabs", [])
        )

        # Strategy 1: Videos tab with richGridRenderer
        videos = _extract_from_rich_grid(tabs, max_videos)
        if videos:
            return videos

        # Strategy 2: Videos tab with gridRenderer
        videos = _extract_from_grid(tabs, max_videos)
        if videos:
            return videos

        # Strategy 3: Home tab with shelfRenderer
        if not videos:
            videos = _extract_from_home_tab(tabs, max_videos)
            if videos:
                return videos

        # Strategy 4: secondaryContents
        if not videos:
            videos = _extract_from_secondary_contents(initial_data, max_videos)

    except Exception as e:
        logger.error(f"Error extracting channel videos: {str(e)}", exc_info=True)
        return []

    return videos[:max_videos] if videos else []


def _extract_from_rich_grid(
    tabs: list[dict[str, Any]], max_videos: int
) -> list[dict[str, Any]]:
    """Extract videos from richGridRenderer in Videos tab."""
    videos: list[dict[str, Any]] = []

    for tab in tabs:
        tab_renderer = tab.get("tabRenderer", {})
        if tab_renderer.get("title") != "Videos":
            continue

        rich_grid = (
            tab_renderer.get("content", {})
            .get("richGridRenderer", {})
            .get("contents", [])
        )

        if not rich_grid:
            continue

        for rich_item in rich_grid[:max_videos * 2]:
            if "richItemRenderer" not in rich_item:
                continue

            video_renderer = (
                rich_item.get("richItemRenderer", {})
                .get("content", {})
                .get("videoRenderer", {})
            )

            if video_renderer:
                video = extract_video_info(video_renderer)
                if video:
                    videos.append(video)
                    if len(videos) >= max_videos:
                        return videos[:max_videos]

        if videos:
            return videos[:max_videos]

    return videos


def _extract_from_grid(
    tabs: list[dict[str, Any]], max_videos: int
) -> list[dict[str, Any]]:
    """Extract videos from gridRenderer in Videos tab."""
    videos: list[dict[str, Any]] = []

    for tab in tabs:
        tab_renderer = tab.get("tabRenderer", {})
        if tab_renderer.get("title") != "Videos":
            continue

        sections = (
            tab_renderer.get("content", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )

        for section in sections:
            item_section = section.get("itemSectionRenderer", {}).get("contents", [])
            for item in item_section:
                grid_renderer = item.get("gridRenderer", {})
                if not grid_renderer:
                    continue

                for grid_item in grid_renderer.get("items", []):
                    video = extract_video_info(
                        grid_item.get("gridVideoRenderer", {})
                    )
                    if video:
                        videos.append(video)
                        if len(videos) >= max_videos:
                            return videos[:max_videos]

        if videos:
            return videos[:max_videos]

    return videos


def _extract_from_home_tab(
    tabs: list[dict[str, Any]], max_videos: int
) -> list[dict[str, Any]]:
    """Extract videos from Home tab shelfRenderer and videoRenderer."""
    videos: list[dict[str, Any]] = []

    for tab in tabs:
        tab_renderer = tab.get("tabRenderer", {})
        if tab_renderer.get("title") != "Home":
            continue

        sections = (
            tab_renderer.get("content", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )

        for section in sections:
            item_section = section.get("itemSectionRenderer", {}).get("contents", [])

            for item in item_section:
                shelf_renderer = item.get("shelfRenderer", {})
                if shelf_renderer:
                    _extract_from_shelf(shelf_renderer, videos, max_videos)
                    if len(videos) >= max_videos:
                        return videos[:max_videos]

                if "videoRenderer" in item:
                    video = extract_video_info(item["videoRenderer"])
                    if video:
                        videos.append(video)
                        if len(videos) >= max_videos:
                            return videos[:max_videos]

            if len(videos) >= max_videos:
                break

        if videos:
            return videos[:max_videos]

    return videos


def _extract_from_shelf(
    shelf_renderer: dict[str, Any],
    videos: list[dict[str, Any]],
    max_videos: int,
) -> None:
    """Extract videos from a shelfRenderer (horizontalList or expandedShelf)."""
    content = shelf_renderer.get("content", {})

    if "horizontalListRenderer" in content:
        items = content["horizontalListRenderer"].get("items", [])
        for list_item in items:
            video_renderer = list_item.get("gridVideoRenderer") or list_item.get(
                "videoRenderer"
            )
            if video_renderer:
                video = extract_video_info(video_renderer)
                if video:
                    videos.append(video)
                    if len(videos) >= max_videos:
                        return

    if "expandedShelfContentsRenderer" in content:
        items = content["expandedShelfContentsRenderer"].get("items", [])
        for list_item in items:
            video_renderer = list_item.get("videoRenderer")
            if video_renderer:
                video = extract_video_info(video_renderer)
                if video:
                    videos.append(video)
                    if len(videos) >= max_videos:
                        return


def _extract_from_secondary_contents(
    initial_data: dict[str, Any], max_videos: int
) -> list[dict[str, Any]]:
    """Extract videos from secondaryContents as last resort."""
    videos: list[dict[str, Any]] = []

    sections = (
        initial_data.get("contents", {})
        .get("twoColumnBrowseResultsRenderer", {})
        .get("secondaryContents", {})
        .get("sectionListRenderer", {})
        .get("contents", [])
    )

    for section in sections:
        if "itemSectionRenderer" not in section:
            continue

        items = section.get("itemSectionRenderer", {}).get("contents", [])
        for item in items:
            if "shelfRenderer" not in item:
                continue

            content = item.get("shelfRenderer", {}).get("content", {})
            if "horizontalListRenderer" not in content:
                continue

            video_items = content.get("horizontalListRenderer", {}).get("items", [])
            for video_item in video_items:
                video = extract_video_info(video_item.get("gridVideoRenderer", {}))
                if video:
                    videos.append(video)
                    if len(videos) >= max_videos:
                        return videos[:max_videos]

    return videos
