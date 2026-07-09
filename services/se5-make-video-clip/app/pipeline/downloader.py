"""
Shorts Downloader — Search, filter, and download YouTube shorts.

Handles HTTP communication with SE6 (search) and SE2 (download),
blacklist filtering, deduplication, and progress reporting.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

logger = get_logger(__name__)

MAX_SEARCH_ATTEMPTS = 5
SEARCH_MULTIPLIER = 3
MAX_POLL_RETRIES = 30
POLL_INTERVAL_SECONDS = 2


class ShortsDownloader:
    """Search and download YouTube shorts with blacklist-aware auto-refill."""

    def __init__(self, settings: Any, status_store: Any) -> None:
        self._settings = settings
        self._status_store = status_store

    async def download_shorts(
        self,
        query: str,
        max_count: int = 50,
        progress_callback: Any = None,
    ) -> list[dict[str, Any]]:
        """
        Download valid (non-blacklisted) shorts with auto-refill.

        Requests 3x max_count from search to compensate for banned videos,
        filters duplicates/approved/rejected, and refills until max_count
        valid downloads are reached.
        """
        logger.info("DOWNLOAD: Searching for %d VALID shorts for '%s'", max_count, query)

        downloaded: list[dict[str, Any]] = []
        search_attempts = 0
        searched_video_ids: set[str] = set()
        search_api_key = self._settings.get('youtube_search_api_key', '') or self._settings.get('api_key', '')
        download_api_key = self._settings.get('video_downloader_api_key', '') or self._settings.get('api_key', '')
        search_headers = {"X-API-Key": search_api_key} if search_api_key else {}
        download_headers = {"X-API-Key": download_api_key} if download_api_key else {}

        try:
            while len(downloaded) < max_count and search_attempts < MAX_SEARCH_ATTEMPTS:
                search_attempts += 1
                videos_still_needed = max_count - len(downloaded)
                search_count = videos_still_needed * SEARCH_MULTIPLIER

                logger.info(
                    "Search attempt #%d: requesting %d shorts (need %d more valid)",
                    search_attempts, search_count, videos_still_needed,
                )

                shorts = await self._search_shorts(query, search_count, search_headers)
                logger.info("  Search returned %d shorts", len(shorts))

                unique_shorts = self._filter_shorts(
                    shorts, searched_video_ids, downloaded, max_count,
                )

                if not unique_shorts:
                    logger.warning(
                        "  No valid shorts after filtering (attempt %d/%d)",
                        search_attempts, MAX_SEARCH_ATTEMPTS,
                    )
                    if search_attempts >= MAX_SEARCH_ATTEMPTS:
                        logger.error("Max search attempts reached, stopping")
                        break
                    continue

                shorts_to_download = unique_shorts[:videos_still_needed]
                logger.info("  Downloading %d shorts...", len(shorts_to_download))

                for short in shorts_to_download:
                    if len(downloaded) >= max_count:
                        break
                    await self._download_single(
                        short, downloaded, max_count, progress_callback, download_headers,
                    )

            logger.info(
                "DOWNLOAD COMPLETE: %d/%d valid downloaded (#%d searches)",
                len(downloaded), max_count, search_attempts,
            )
            return downloaded

        except Exception as e:
            logger.error("Error during download: %s", e, exc_info=True)
            return downloaded

    async def _search_shorts(
        self, query: str, search_count: int, headers: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Execute search via SE6 youtube-search service."""
        youtube_search_url = self._settings.get('youtube_search_url')

        async with httpx.AsyncClient(timeout=120.0, headers=headers) as client:
            response = await client.post(
                f"{youtube_search_url}/search/shorts",
                params={"query": query, "max_results": search_count},
            )
            response.raise_for_status()
            job_data = response.json()
            job_id = job_data.get('id')

            logger.info("  Search job: %s", job_id)

            wait_response = await client.get(
                f"{youtube_search_url}/jobs/{job_id}/wait",
                timeout=90.0,
            )
            wait_response.raise_for_status()
            completed_job = wait_response.json()

        return completed_job.get('result', {}).get('results', [])

    def _filter_shorts(
        self,
        shorts: list[dict[str, Any]],
        searched_video_ids: set[str],
        already_downloaded: list[dict[str, Any]],
        max_count: int,
    ) -> list[dict[str, Any]]:
        """Filter shorts: deduplicate, skip approved/blacklisted/already-searched."""
        unique_shorts = []
        seen_video_ids = set()
        already_downloaded_ids = {s['video_id'] for s in already_downloaded}
        duplicated = 0
        already_approved = 0
        already_rejected = 0
        already_searched = 0

        for short in shorts:
            video_id = short.get('video_id')
            if not video_id:
                continue

            if video_id in seen_video_ids:
                duplicated += 1
                continue
            seen_video_ids.add(video_id)

            if video_id in searched_video_ids or video_id in already_downloaded_ids:
                already_searched += 1
                continue
            searched_video_ids.add(video_id)

            if Path(f"data/approved/videos/{video_id}.mp4").exists():
                already_approved += 1
                logger.debug("  %s: already approved (skip)", video_id)
                continue

            if self._status_store.is_rejected(video_id):
                already_rejected += 1
                logger.debug("  %s: blacklisted (skip)", video_id)
                continue

            unique_shorts.append(short)

        logger.info(
            "  Filtered: %d valid | %d dup | %d re-search | %d approved | %d blacklisted",
            len(unique_shorts), duplicated, already_searched, already_approved, already_rejected,
        )
        return unique_shorts

    async def _download_single(
        self,
        short: dict[str, Any],
        downloaded: list[dict[str, Any]],
        max_count: int,
        progress_callback: Any,
        headers: dict[str, str],
    ) -> None:
        """Download a single short via SE2 video-downloader service."""
        video_id = short.get('video_id')
        video_downloader_url = self._settings.get('video_downloader_url')

        try:
            async with httpx.AsyncClient(timeout=120.0, headers=headers) as client:
                response = await client.post(
                    f"{video_downloader_url}/jobs",
                    json={"url": f"https://www.youtube.com/watch?v={video_id}", "quality": "best"},
                )
                response.raise_for_status()
                job = response.json()
                job_id = job.get('id')

                logger.info(
                    "  [%d/%d] %s: job %s",
                    len(downloaded) + 1, max_count, video_id, job_id,
                )

                file_path = await self._poll_download(client, video_downloader_url, job_id)

                download_response = await client.get(
                    f"{video_downloader_url}/jobs/{job_id}/download",
                    timeout=60.0,
                )
                download_response.raise_for_status()

            file_ext = Path(file_path).suffix if file_path else ".mp4"
            video_path = Path(f"data/raw/shorts/{video_id}{file_ext}")
            video_path.parent.mkdir(parents=True, exist_ok=True)

            with open(video_path, 'wb') as f:
                f.write(download_response.content)

            logger.info("  [%d/%d] %s: saved", len(downloaded) + 1, max_count, video_id)

            downloaded.append({
                'video_id': video_id,
                'title': short.get('title'),
                'raw_path': str(video_path),
                'downloaded_at': now_brazil().isoformat(),
            })

            if progress_callback:
                progress_pct = 10 + (len(downloaded) / max_count * 40)
                try:
                    await progress_callback(
                        progress=progress_pct,
                        metadata={
                            'step': 'downloading_shorts',
                            'downloaded': len(downloaded),
                            'total': max_count,
                            'current_video': video_id,
                        },
                    )
                except Exception as e:
                    logger.warning("Callback error: %s", e)

        except Exception as e:
            logger.error("  [%d/%d] %s: %s", len(downloaded) + 1, max_count, video_id, e)

    async def _poll_download(
        self, client: httpx.AsyncClient, base_url: str, job_id: str,
    ) -> str:
        """Poll SE2 until download job completes or fails."""
        for _ in range(MAX_POLL_RETRIES):
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            status_response = await client.get(f"{base_url}/jobs/{job_id}")
            status_response.raise_for_status()
            job_status = status_response.json()

            if job_status.get('status') == 'completed':
                return job_status.get('file_path', '')
            elif job_status.get('status') == 'failed':
                error_msg = job_status.get('error_message', 'Unknown')
                raise Exception(f"Download failed: {error_msg}")

        raise Exception("Download timeout (60s)")
