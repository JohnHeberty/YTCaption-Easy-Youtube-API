import re
import json
from urllib.parse import quote_plus

from .utils import fetch_url, get_thumbnail_urls, extract_initial_data


def _extract_search_video_details(video_renderer):
    """Extract basic details from a video renderer in search results"""
    if not video_renderer:
        return None

    video_id = video_renderer.get("videoId")
    if not video_id:
        return None

    video_info = {
        "video_id": video_id,
        "thumbnails": get_thumbnail_urls(video_id),
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }

    title_runs = video_renderer.get("title", {}).get("runs", [])
    if title_runs:
        video_info["title"] = "".join(run.get("text", "") for run in title_runs)

    view_count_text = video_renderer.get("viewCountText", {}).get("simpleText", "")
    if view_count_text:
        view_match = re.search(r"(\d+(?:,\d+)*)", view_count_text)
        if view_match:
            video_info["views"] = int(view_match.group(1).replace(",", ""))

    published_time = video_renderer.get("publishedTimeText", {}).get("simpleText", "")
    if published_time:
        video_info["published_time"] = published_time

    return video_info


def _extract_channel_info(video_renderer, video_info):
    """Extract channel information from video renderer"""
    owner_text = video_renderer.get("ownerText", {}).get("runs", [])
    if owner_text:
        video_info["channel_name"] = owner_text[0].get("text", "")
        owner_endpoint = owner_text[0].get("navigationEndpoint", {})
        browse_id = owner_endpoint.get("browseEndpoint", {}).get("browseId")
        if browse_id:
            video_info["channel_id"] = browse_id
            video_info["channel_url"] = f"https://www.youtube.com/channel/{browse_id}"
    return video_info


def _extract_video_duration(video_renderer, video_info):
    """Extract and process video duration information"""
    duration_text = video_renderer.get("lengthText", {}).get("simpleText", "")
    if duration_text:
        video_info["duration"] = duration_text
        time_parts = duration_text.split(":")
        duration_seconds = 0
        if len(time_parts) == 3:
            duration_seconds = (
                int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])
            )
        elif len(time_parts) == 2:
            duration_seconds = int(time_parts[0]) * 60 + int(time_parts[1])
        elif len(time_parts) == 1:
            duration_seconds = int(time_parts[0])
        video_info["duration_seconds"] = duration_seconds
    return video_info


def _extract_video_status(video_renderer, video_info):
    """Extract video status information (live, upcoming, etc.)"""
    badges = video_renderer.get("badges", [])
    if badges:
        video_info["badges"] = [
            badge.get("metadataBadgeRenderer", {}).get("label", "") for badge in badges
        ]

    video_info["is_live"] = bool(
        badges
        and any(
            "LIVE" in badge.get("metadataBadgeRenderer", {}).get("label", "")
            for badge in badges
        )
    )

    thumbnail_overlays = video_renderer.get("thumbnailOverlays", [])
    for overlay in thumbnail_overlays:
        if "thumbnailOverlayTimeStatusRenderer" in overlay:
            status = overlay["thumbnailOverlayTimeStatusRenderer"].get("style", "")
            if status == "LIVE":
                video_info["is_live"] = True
            elif status == "UPCOMING":
                video_info["is_upcoming"] = True

    return video_info


def _extract_additional_details(video_renderer, video_info):
    """Extract additional video details"""
    description_snippet = video_renderer.get("detailedMetadataSnippets", [])
    if description_snippet:
        snippet_text = description_snippet[0].get("snippetText", {}).get("runs", [])
        if snippet_text:
            video_info["description_snippet"] = "".join(
                run.get("text", "") for run in snippet_text
            )

    rich_thumbnail = (
        video_renderer.get("richThumbnail", {})
        .get("movingThumbnailRenderer", {})
        .get("movingThumbnailDetails", {})
        .get("thumbnails", [])
    )
    if rich_thumbnail:
        video_info["rich_thumbnail_url"] = rich_thumbnail[0].get("url")

    return video_info


def _extract_continuation_token(initial_data):
    """Extract the continuation token for the next page of results"""
    try:
        contents = (
            initial_data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )

        for content in contents:
            if "continuationItemRenderer" in content:
                return content["continuationItemRenderer"]["continuationEndpoint"][
                    "continuationCommand"
                ]["token"]

        for content in contents:
            if "itemSectionRenderer" in content:
                section_contents = content["itemSectionRenderer"].get("contents", [])
                for section_content in section_contents:
                    if "continuationItemRenderer" in section_content:
                        return section_content["continuationItemRenderer"][
                            "continuationEndpoint"
                        ]["continuationCommand"]["token"]

        return None
    except Exception:
        return None


def _process_search_results(initial_data, max_results=10):
    """Process YouTube search results from initial data"""
    search_results = []
    continuation_token = None

    try:
        contents = (
            initial_data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )

        for content in contents:
            item_section = content.get("itemSectionRenderer", {})
            if item_section:
                items = item_section.get("contents", [])

                for item in items:
                    video_renderer = item.get("videoRenderer", {})

                    video_info = _extract_search_video_details(video_renderer)
                    if not video_info:
                        continue

                    video_info = _extract_channel_info(video_renderer, video_info)
                    video_info = _extract_video_duration(video_renderer, video_info)
                    video_info = _extract_video_status(video_renderer, video_info)
                    video_info = _extract_additional_details(video_renderer, video_info)

                    search_results.append(video_info)

                    if len(search_results) >= max_results:
                        break

                if len(search_results) >= max_results:
                    break

            if (
                "continuationItemRenderer" in content
                and len(search_results) < max_results
            ):
                continuation_token = content["continuationItemRenderer"][
                    "continuationEndpoint"
                ]["continuationCommand"]["token"]

        if continuation_token is None and len(search_results) < max_results:
            continuation_token = _extract_continuation_token(initial_data)

    except Exception as e:
        return {"error": f"Error parsing search results: {str(e)}"}, None

    return search_results, continuation_token


def _fetch_continuation_page(continuation_token, timeout=10):
    """Fetch the next page of search results using the continuation token"""
    if not continuation_token:
        return {"error": "No continuation token provided"}, None

    continuation_url = "https://www.youtube.com/youtubei/v1/search?key=AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"

    headers = {
        "X-YouTube-Client-Name": "1",
        "X-YouTube-Client-Version": "2.20200720.00.00",
        "Content-Type": "application/json",
    }

    data = {
        "context": {
            "client": {"clientName": "WEB", "clientVersion": "2.20200720.00.00"}
        },
        "continuation": continuation_token,
    }

    response = fetch_url(
        continuation_url,
        timeout=timeout,
        method="POST",
        headers=headers,
        json_data=data,
    )

    if not response:
        return {"error": "Failed to fetch continuation page"}, None

    try:
        response_data = json.loads(response)

        items = (
            response_data.get("onResponseReceivedCommands", [])[0]
            .get("appendContinuationItemsAction", {})
            .get("continuationItems", [])
        )

        results = []
        next_continuation = None

        for item in items:
            if "itemSectionRenderer" in item:
                section_contents = item["itemSectionRenderer"].get("contents", [])
                for content in section_contents:
                    video_renderer = content.get("videoRenderer", {})

                    video_info = _extract_search_video_details(video_renderer)
                    if not video_info:
                        continue

                    video_info = _extract_channel_info(video_renderer, video_info)
                    video_info = _extract_video_duration(video_renderer, video_info)
                    video_info = _extract_video_status(video_renderer, video_info)
                    video_info = _extract_additional_details(video_renderer, video_info)

                    results.append(video_info)

            elif "continuationItemRenderer" in item:
                next_continuation = item["continuationItemRenderer"][
                    "continuationEndpoint"
                ]["continuationCommand"]["token"]

        return results, next_continuation

    except Exception as e:
        return {"error": f"Error parsing continuation results: {str(e)}"}, None


def search_youtube(query, max_results=10, timeout=10):
    """Search YouTube and return detailed information about multiple videos with minimal requests"""
    if not query:
        return {"error": "No search query provided"}

    encoded_query = quote_plus(query)
    search_url = f"https://www.youtube.com/results?search_query={encoded_query}"

    html_content = fetch_url(search_url, timeout=timeout)
    if not html_content:
        return {"error": "Failed to fetch search results"}

    initial_data = extract_initial_data(html_content)
    if not initial_data:
        return {"error": "Failed to extract search data"}

    results, continuation_token = _process_search_results(initial_data, max_results)
    if isinstance(results, dict) and "error" in results:
        return results

    all_results = results.copy()
    page_count = 1

    while continuation_token and len(all_results) < max_results:
        next_page_results, next_continuation = _fetch_continuation_page(
            continuation_token, timeout
        )

        if isinstance(next_page_results, dict) and "error" in next_page_results:
            break

        all_results.extend(next_page_results[: max_results - len(all_results)])
        continuation_token = next_continuation
        page_count += 1

        if page_count >= 10:
            break

    return {
        "query": query,
        "results_count": len(all_results),
        "pages_fetched": page_count,
        "results": all_results[:max_results],
    }


def _extract_reel_item_details(reel_renderer):
    """
    Extract details from reelItemRenderer (shorts-specific structure)
    
    YouTube uses reelItemRenderer for shorts in some contexts
    """
    if not reel_renderer:
        return None
    
    video_id = reel_renderer.get("videoId")
    if not video_id:
        return None
    
    short_info = {
        "video_id": video_id,
        "thumbnails": get_thumbnail_urls(video_id),
        "url": f"https://www.youtube.com/shorts/{video_id}",
        "is_short": True
    }
    
    # Extract title
    headline = reel_renderer.get("headline", {})
    if headline:
        title_runs = headline.get("runs", [])
        if title_runs:
            short_info["title"] = "".join(run.get("text", "") for run in title_runs)
        else:
            simple_text = headline.get("simpleText", "")
            if simple_text:
                short_info["title"] = simple_text
    
    # Extract view count
    view_count_text = reel_renderer.get("viewCountText", {}).get("simpleText", "")
    if view_count_text:
        view_match = re.search(r"(\d+(?:,\d+)*)", view_count_text)
        if view_match:
            short_info["views"] = int(view_match.group(1).replace(",", ""))
            short_info["view_count_text"] = view_count_text
    
    # Shorts are always 60 seconds or less
    short_info["duration_seconds"] = 60  # Approximate, actual may be less
    
    return short_info


def search_shorts(query, max_results=10, timeout=10):
    """
    Search specifically for YouTube Shorts
    
    Strategy:
    1. Add 'shorts' to search query to bias results
    2. Perform regular search with higher limit
    3. Filter results by duration (≤60s)
    4. Continue pagination until enough shorts found
    
    Args:
        query: Search query string
        max_results: Number of shorts to return
        timeout: Request timeout in seconds
        
    Returns:
        Dictionary with shorts search results
    """
    if not query:
        return {"error": "No search query provided"}
    
    # Enhance query to find shorts
    enhanced_query = f"{query} shorts"
    
    # Fetch more results than needed (will filter for shorts)
    fetch_count = max_results * 3  # Over-fetch to ensure enough shorts
    
    # Perform regular search
    results = search_youtube(enhanced_query, fetch_count, timeout)
    
    if results.get('error'):
        return results
    
    # Filter for shorts only (duration ≤ 60 seconds)
    all_videos = results.get('results', [])
    shorts_only = []
    
    for video in all_videos:
        duration_seconds = video.get('duration_seconds', 999)
        url = video.get('url', '')
        
        # Check if it's a short by duration or URL
        if duration_seconds <= 60 or '/shorts/' in url:
            video['is_short'] = True
            shorts_only.append(video)
            
            if len(shorts_only) >= max_results:
                break
    
    return {
        "query": query,
        "search_type": "shorts",
        "results_count": len(shorts_only),
        "total_scanned": len(all_videos),
        "pages_fetched": results.get('pages_fetched', 1),
        "results": shorts_only[:max_results]
    }


def filter_videos_by_type(videos, shorts_only=False, exclude_shorts=False):
    """
    Filter video list based on shorts preferences
    
    Args:
        videos: List of video dictionaries
        shorts_only: If True, return only shorts
        exclude_shorts: If True, exclude shorts from results
        
    Returns:
        Filtered list of videos
    """
    if not shorts_only and not exclude_shorts:
        return videos
    
    filtered = []
    
    for video in videos:
        duration_seconds = video.get('duration_seconds', 999)
        url = video.get('url', '')
        is_short = duration_seconds <= 60 or '/shorts/' in url
        
        if shorts_only and is_short:
            video['is_short'] = True
            filtered.append(video)
        elif exclude_shorts and not is_short:
            video['is_short'] = False
            filtered.append(video)
        elif not shorts_only and not exclude_shorts:
            video['is_short'] = is_short
            filtered.append(video)
    
    return filtered
