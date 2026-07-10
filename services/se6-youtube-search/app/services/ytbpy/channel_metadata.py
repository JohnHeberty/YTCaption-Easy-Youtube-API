from __future__ import annotations

import re
from typing import Any
from common.log_utils import get_logger

from .channel_parsers import extract_text, parse_count

logger = get_logger(__name__)


def extract_channel_metadata(initial_data: dict[str, Any]) -> dict[str, Any]:
    """Extract metadata about the channel using the new YouTube data structure"""
    channel_info: dict[str, Any] = {}

    try:
        page_header = initial_data.get("header", {}).get("pageHeaderRenderer", {})
        c4_header = initial_data.get("header", {}).get("c4TabbedHeaderRenderer", {})
        channel_metadata = initial_data.get("metadata", {}).get(
            "channelMetadataRenderer", {}
        )
        microformat = initial_data.get("microformat", {}).get(
            "microformatDataRenderer", {}
        )

        if channel_metadata and channel_metadata.get("description"):
            channel_info["description"] = channel_metadata.get("description", "")
        elif microformat and microformat.get("description"):
            channel_info["description"] = microformat.get("description", "")

        if page_header:
            _extract_from_page_header(channel_info, page_header)

        if c4_header and not channel_info.get("title"):
            _extract_from_c4_header(channel_info, c4_header)

        if channel_metadata:
            _extract_from_channel_metadata(channel_info, channel_metadata)

        _extract_from_about_tab(channel_info, initial_data)

        if "description" in channel_info and not channel_info.get(
            "description_snippet"
        ):
            channel_info["description_snippet"] = (
                channel_info["description"][:150] + "..."
                if len(channel_info["description"]) > 150
                else channel_info["description"]
            )

        return channel_info
    except Exception as e:
        return {"error": f"Error extracting channel metadata: {str(e)}"}


def _extract_from_page_header(
    channel_info: dict[str, Any], page_header: dict[str, Any]
) -> None:
    """Extract metadata from pageHeaderRenderer structure."""
    page_header_view_model = page_header.get("content", {}).get(
        "pageHeaderViewModel", {}
    )

    # Title
    dynamic_title = page_header_view_model.get("title", {}).get(
        "dynamicTextViewModel", {}
    )
    if (
        dynamic_title
        and "text" in dynamic_title
        and "content" in dynamic_title["text"]
    ):
        channel_info["title"] = dynamic_title["text"]["content"]
    else:
        channel_info["title"] = page_header.get("pageTitle", "")

    # Description
    desc_view_model = page_header_view_model.get("description", {}).get(
        "descriptionPreviewViewModel", {}
    )
    if desc_view_model and "description" in desc_view_model:
        if not channel_info.get("description"):
            channel_info["description"] = desc_view_model["description"].get(
                "content", ""
            )
        channel_info["description_snippet"] = desc_view_model["description"].get(
            "content", ""
        )

    # Avatar
    avatar_view_model = page_header_view_model.get("image", {}).get(
        "decoratedAvatarViewModel", {}
    )
    if avatar_view_model:
        avatar_sources = (
            avatar_view_model.get("avatar", {})
            .get("avatarViewModel", {})
            .get("image", {})
            .get("sources", [])
        )
        if avatar_sources:
            channel_info["avatar_thumbnails"] = avatar_sources
            channel_info["logo_url"] = avatar_sources[-1].get("url", "")

    # Banner
    banner_view_model = page_header_view_model.get("banner", {}).get(
        "imageBannerViewModel", {}
    )
    if banner_view_model and "image" in banner_view_model:
        banner_sources = banner_view_model["image"].get("sources", [])
        if banner_sources:
            channel_info["banner_thumbnails"] = banner_sources
            channel_info["banner_url"] = banner_sources[-1].get("url", "")

    # Metadata rows
    metadata_rows = (
        page_header_view_model.get("metadata", {})
        .get("contentMetadataViewModel", {})
        .get("metadataRows", [])
    )

    for row in metadata_rows:
        if "metadataRowViewModel" in row:
            row_model = row["metadataRowViewModel"]
            title = extract_text(row_model.get("title", {})).lower()
            content = extract_text(row_model.get("content", {}))

            if not content:
                continue

            if "subscriber" in title or "sub" in title:
                channel_info["subscriber_count_text"] = content
                channel_info["subscriber_count_approximate"] = parse_count(content)
            elif "video" in title:
                try:
                    channel_info["video_count"] = int(
                        re.search(r"([\d,]+)", content).group(1).replace(",", "")
                    )
                except (AttributeError, ValueError):
                    pass
            elif "view" in title:
                try:
                    channel_info["view_count"] = int(
                        re.search(r"([\d,]+)", content).group(1).replace(",", "")
                    )
                except (AttributeError, ValueError):
                    pass
            elif "join" in title:
                channel_info["joined_date"] = content
            elif "location" in title or "country" in title:
                channel_info["location"] = content

    # Handle / vanity URL
    try:
        attribution_vm = page_header_view_model.get("attribution", {}).get(
            "attributionViewModel", {}
        )
        if attribution_vm and "text" in attribution_vm:
            attribution_text = extract_text(attribution_vm["text"])
            handle_match = re.search(r"@([a-zA-Z0-9_.-]+)", attribution_text)
            if handle_match:
                handle_name = handle_match.group(1)
                channel_info["handle_name"] = handle_name
                channel_info["handle"] = f"@{handle_name}"
                channel_info["vanity_url"] = (
                    f"https://www.youtube.com/@{handle_name}"
                )
    except Exception:
        pass


def _extract_from_c4_header(
    channel_info: dict[str, Any], c4_header: dict[str, Any]
) -> None:
    """Extract metadata from c4TabbedHeaderRenderer structure."""
    channel_info["title"] = c4_header.get("title", "")

    vanity_channel = (
        c4_header.get("navigationEndpoint", {})
        .get("browseEndpoint", {})
        .get("canonicalBaseUrl", "")
    )
    if vanity_channel:
        channel_info["handle"] = vanity_channel
        if vanity_channel.startswith("/@"):
            channel_info["handle_name"] = vanity_channel[2:]
            channel_info["vanity_url"] = (
                f"https://www.youtube.com{vanity_channel}"
            )

    if c4_header.get("descriptionSnippet", {}).get("runs"):
        channel_info["description_snippet"] = "".join(
            run.get("text", "")
            for run in c4_header.get("descriptionSnippet", {}).get("runs", [])
        )
        if not channel_info.get("description"):
            channel_info["description"] = channel_info["description_snippet"]

    if not channel_info.get("logo_url") and c4_header.get("avatar", {}).get(
        "thumbnails"
    ):
        channel_info["avatar_thumbnails"] = c4_header.get("avatar", {}).get(
            "thumbnails", []
        )
        if channel_info["avatar_thumbnails"]:
            channel_info["logo_url"] = channel_info["avatar_thumbnails"][-1].get(
                "url"
            )

    if not channel_info.get("banner_url") and c4_header.get("banner", {}).get(
        "thumbnails"
    ):
        channel_info["banner_thumbnails"] = c4_header.get("banner", {}).get(
            "thumbnails", []
        )
        if channel_info["banner_thumbnails"]:
            channel_info["banner_url"] = channel_info["banner_thumbnails"][-1].get(
                "url"
            )

    if not channel_info.get("subscriber_count_text"):
        subscriber_count_text = extract_text(
            c4_header.get("subscriberCountText", {})
        )
        if subscriber_count_text:
            channel_info["subscriber_count_text"] = subscriber_count_text
            channel_info["subscriber_count_approximate"] = parse_count(
                subscriber_count_text
            )

        metadata_rows = (
            c4_header.get("metadataRowContainer", {})
            .get("metadataRowContainerRenderer", {})
            .get("rows", [])
        )

        for row in metadata_rows:
            row_renderer = row.get("metadataRowRenderer", {})
            title = extract_text(row_renderer.get("title", {})).lower()
            contents = extract_text(row_renderer.get("contents", [{}])[0])

            if not contents:
                continue

            if "video" in title and not channel_info.get("video_count"):
                try:
                    channel_info["video_count"] = int(
                        re.search(r"([\d,]+)", contents).group(1).replace(",", "")
                    )
                except (AttributeError, ValueError):
                    pass
            elif "view" in title and not channel_info.get("view_count"):
                try:
                    channel_info["view_count"] = int(
                        re.search(r"([\d,]+)", contents).group(1).replace(",", "")
                    )
                except (AttributeError, ValueError):
                    pass
            elif "join" in title and not channel_info.get("joined_date"):
                channel_info["joined_date"] = contents
            elif "location" in title and not channel_info.get("location"):
                channel_info["location"] = contents


def _extract_from_channel_metadata(
    channel_info: dict[str, Any], channel_metadata: dict[str, Any]
) -> None:
    """Extract metadata from channelMetadataRenderer structure."""
    if not channel_info.get("title"):
        channel_info["title"] = channel_metadata.get("title", "")

    if not channel_info.get("logo_url") and channel_metadata.get(
        "avatar", {}
    ).get("thumbnails"):
        channel_info["avatar_thumbnails"] = channel_metadata.get(
            "avatar", {}
        ).get("thumbnails", [])
        if channel_info["avatar_thumbnails"]:
            channel_info["logo_url"] = channel_info["avatar_thumbnails"][-1].get(
                "url"
            )

    if channel_metadata.get("vanityChannelUrl") and not channel_info.get(
        "vanity_url"
    ):
        vanity_url = channel_metadata.get("vanityChannelUrl")
        channel_info["vanity_url"] = vanity_url
        if "/@" in vanity_url:
            handle_name = vanity_url.split("/@")[-1]
            channel_info["handle_name"] = handle_name
            channel_info["handle"] = f"@{handle_name}"

    if not channel_info.get("channel_id"):
        channel_info["channel_id"] = channel_metadata.get("externalId", "")


def _extract_from_about_tab(
    channel_info: dict[str, Any], initial_data: dict[str, Any]
) -> None:
    """Extract metadata from the About tab."""
    for tab in (
        initial_data.get("contents", {})
        .get("twoColumnBrowseResultsRenderer", {})
        .get("tabs", [])
    ):
        tab_renderer = tab.get("tabRenderer", {})
        if tab_renderer.get("title") == "About":
            sections = (
                tab_renderer.get("content", {})
                .get("sectionListRenderer", {})
                .get("contents", [])
            )
            for section in sections:
                items = section.get("itemSectionRenderer", {}).get("contents", [])
                for item in items:
                    about_renderer = item.get(
                        "channelAboutFullMetadataRenderer", {}
                    )
                    if about_renderer:
                        _parse_about_renderer(channel_info, about_renderer)


def _parse_about_renderer(
    channel_info: dict[str, Any], about_renderer: dict[str, Any]
) -> None:
    """Parse channelAboutFullMetadataRenderer into channel_info fields."""
    if not channel_info.get("description") and about_renderer.get(
        "description", {}
    ).get("simpleText"):
        channel_info["description"] = about_renderer.get("description", {}).get(
            "simpleText", ""
        )

    if not channel_info.get("video_count") and "videoCountText" in about_renderer:
        video_count_text = extract_text(about_renderer.get("videoCountText", {}))
        video_count_match = re.search(r"([\d,]+)", video_count_text)
        if video_count_match:
            channel_info["video_count"] = int(
                video_count_match.group(1).replace(",", "")
            )

    if not channel_info.get("view_count") and "viewCountText" in about_renderer:
        view_count_text = extract_text(about_renderer.get("viewCountText", {}))
        view_count_match = re.search(r"([\d,]+)", view_count_text)
        if view_count_match:
            channel_info["view_count"] = int(
                view_count_match.group(1).replace(",", "")
            )

    if not channel_info.get("joined_date") and "joinedDateText" in about_renderer:
        channel_info["joined_date"] = extract_text(
            about_renderer.get("joinedDateText", {})
        )

    if not channel_info.get("location") and "country" in about_renderer:
        channel_info["location"] = extract_text(about_renderer.get("country", {}))

    external_links: list[dict[str, str]] = []
    for link in about_renderer.get("primaryLinks", []):
        title = extract_text(link.get("title", {}))
        url = (
            link.get("navigationEndpoint", {})
            .get("urlEndpoint", {})
            .get("url", "")
        )
        if title and url:
            external_links.append({"title": title, "url": url})

    if external_links:
        channel_info["external_links"] = external_links

    if not channel_info.get("vanity_url") and about_renderer.get("channelId"):
        channel_id = about_renderer.get("channelId")
        if channel_id:
            channel_info["channel_id"] = channel_id

            for link in about_renderer.get("primaryLinks", []):
                url = (
                    link.get("navigationEndpoint", {})
                    .get("urlEndpoint", {})
                    .get("url", "")
                )
                if "youtube.com/" in url and "/@" in url:
                    channel_info["vanity_url"] = url
                    handle_name = url.split("/@")[-1].split("?")[0]
                    channel_info["handle_name"] = handle_name
                    channel_info["handle"] = f"@{handle_name}"
                    break
