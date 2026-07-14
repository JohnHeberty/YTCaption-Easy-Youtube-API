from __future__ import annotations

import re
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import socket
from datetime import datetime
from typing import Any
import os
from common.log_utils import get_logger

logger = get_logger(__name__)

proxys: list[dict[str, Any]] = []
if os.path.exists("proxies.txt"):
    with open("proxies.txt", "r") as file:
        proxys_raw: list[list[str]] = [row.strip().split(":") for row in file.readlines()]
        if proxys_raw:
            # proxy[0] : 23.95.150.145
            # proxy[1] : 6114
            # proxy[2] : qobuswsu
            # proxy[3] : nd9ne57aazbx
            proxys = [
                {
                    "http": f"http://{proxy[2]}:{proxy[3]}@{proxy[0]}:{proxy[1]}/",
                    "https": f"http://{proxy[2]}:{proxy[3]}@{proxy[0]}:{proxy[1]}/",
                    "live": True
                }
            for proxy in proxys_raw
            ]

def next_proxie() -> bool:
    """Disable proxy settings"""
    global proxys
    if proxys:
        choice_proxy = [(row, index) for row, index in zip(proxys, range(len(proxys))) if row.get("live", True)]
        if choice_proxy:
            _, index = choice_proxy[0]
            proxys[index]["live"] = False
            return True
    return False

def get_thumbnail_urls(video_id: str) -> dict[str, dict[str, Any]]:
    """Generate thumbnail URLs for a YouTube video"""
    base_url = f"https://img.youtube.com/vi/{video_id}"
    return {
        "default": {"url": f"{base_url}/default.jpg", "width": 120, "height": 90},
        "medium": {"url": f"{base_url}/mqdefault.jpg", "width": 320, "height": 180},
        "high": {"url": f"{base_url}/hqdefault.jpg", "width": 480, "height": 360},
        "standard": {"url": f"{base_url}/sddefault.jpg", "width": 640, "height": 480},
        "maxres": {
            "url": f"{base_url}/maxresdefault.jpg",
            "width": 1280,
            "height": 720,
        },
    }


def fetch_url(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 5,
    method: str = "GET",
    json_data: dict[str, Any] | None = None,
) -> str | None:
    """Fetch content from a URL"""
    if headers is None:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }

    try:
        data = None
        if json_data:
            data = json.dumps(json_data).encode("utf-8")
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"

        # Initialize request object
        req = Request(url, headers=headers, method=method, data=data)
        
        # If proxies are available and active, use them
        if proxys:
            choice_proxy = [row for row in proxys if row.get("live", True)]
            if choice_proxy:
                proxy = choice_proxy[0]
                req = Request(url, headers=headers, method=method, data=data, proxies=proxy)

        with urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="ignore")
    except (URLError, HTTPError, socket.timeout):
        return None


def extract_json_data(html_content: str | None, pattern: str) -> Any | None:
    """Helper to extract JSON data using regex pattern"""
    if not html_content:
        return None

    match = re.search(pattern, html_content)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def extract_initial_data(html_content: str | None) -> dict[str, Any] | None:
    """Extract initial data from HTML content"""
    return extract_json_data(html_content, r"ytInitialData\s*=\s*({.+?});</script>")


def parse_duration_to_seconds(duration_text: str | None) -> int | None:
    """Parse duration text to seconds"""
    if not duration_text:
        return None

    parts = duration_text.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    if len(parts) == 2:
        minutes, seconds = int(parts[0]), int(parts[1])
        return minutes * 60 + seconds
    if len(parts) == 1:
        return int(parts[0])
    return None


def parse_iso8601_date(date_string: str) -> int | None:
    """Parse ISO 8601 date to timestamp."""
    return int(datetime.fromisoformat(date_string).timestamp()) if date_string else None


def parse_view_count(view_count_text: str) -> int | None:
    """Convert view count text like '1,072,836,095 views' to integer."""
    if not view_count_text:
        return None

    view_count_text = view_count_text.replace("views", "").strip()

    try:
        return int(view_count_text.replace(",", ""))
    except (ValueError, TypeError):
        return None


_DEFAULT_INNERTUBE_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"


def get_innertube_api_key() -> str:
    """Return YouTube InnerTube API key from config, with safe fallback."""
    try:
        from app.core.config import get_settings
        return get_settings().youtube_innertube_api_key
    except Exception as e:
        logger.debug("Failed to load innertube API key from settings: %s", e)
        return _DEFAULT_INNERTUBE_KEY
