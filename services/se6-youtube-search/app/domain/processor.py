from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from common.datetime_utils import now_brazil

from .models import Job, JobStatus, SearchType
from ..shared.exceptions import YouTubeSearchException, YouTubeAPIError
from ..core.config import get_settings

# Import ytbpy functions
from ..services.ytbpy import video as ytb_video
from ..services.ytbpy import channel as ytb_channel
from ..services.ytbpy import playlist as ytb_playlist
from ..services.ytbpy import search as ytb_search
from common.log_utils import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Tenacity retry policy for synchronous ytbpy calls
# - 3 attempts, exponential backoff 1–10s, retries on ANY exception, reraises
# ---------------------------------------------------------------------------
_YTBPY_RETRY = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

@retry(**_YTBPY_RETRY)
def _ytbpy_call(func: Callable[..., Any], *args: Any) -> Any:
    """Execute a synchronous ytbpy function with tenacity retry."""
    return func(*args)

class YouTubeSearchProcessor:
    """
    Processor for YouTube search operations using ytbpy library
    """
    
    def __init__(self) -> None:
        self.settings = get_settings()
        self.timeout = self.settings.youtube_default_timeout
        self.job_store = None  # Will be injected by main.py
        logger.info("✅ YouTube Search Processor initialized")
    
    async def process_search_job(self, job: Job) -> Job:
        """Process a search job asynchronously.

        Args:
            job: Job object with search parameters

        Returns:
            Updated Job object with results
        """
        try:
            logger.info("Processing search job %s - Type: %s", job.id, job.search_type.value)
            
            # Update job status to processing
            job.status = JobStatus.PROCESSING
            job.progress = 10.0
            if self.job_store:
                self.job_store.update_job(job)
            
            # Execute search based on type
            result = None
            
            if job.search_type == SearchType.VIDEO_INFO:
                result = await self._get_video_info(job.video_id)
            elif job.search_type == SearchType.CHANNEL_INFO:
                result = await self._get_channel_info(job.channel_id, job.include_videos)
            elif job.search_type == SearchType.PLAYLIST_INFO:
                result = await self._get_playlist_info(job.playlist_id)
            elif job.search_type == SearchType.VIDEO:
                result = await self._search_videos(job.query, job.max_results)
            elif job.search_type == SearchType.RELATED_VIDEOS:
                result = await self._get_related_videos(job.video_id, job.max_results)
            elif job.search_type == SearchType.SHORTS:
                result = await self._search_shorts(job.query, job.max_results)
            else:
                raise YouTubeSearchException(f"Unsupported search type: {job.search_type}")
            
            job.progress = 90.0
            if self.job_store:
                self.job_store.update_job(job)
            
            # Update job with results
            job.result = result
            job.status = JobStatus.COMPLETED
            job.progress = 100.0
            job.completed_at = now_brazil()
            
            if self.job_store:
                self.job_store.update_job(job)
            
            logger.info("Job %s completed successfully", job.id)
            return job
            
        except Exception as e:
            logger.error("Error processing job %s: %s", job.id, e, exc_info=True)
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = now_brazil()
            
            if self.job_store:
                self.job_store.update_job(job)
            
            return job
    
    async def _get_video_info(self, video_id: str) -> dict[str, Any]:
        """Get video information."""
        try:
            logger.info("Fetching video info: %s", video_id)
            
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                _ytbpy_call,
                ytb_video.get_video_info,
                video_id,
                self.timeout
            )
            
            if result.get('error'):
                raise YouTubeAPIError(result['error'])
            
            return result
            
        except Exception as e:
            logger.error("Error fetching video info: %s", e)
            raise YouTubeAPIError(f"Failed to get video info: {e}")
    
    async def _get_channel_info(self, channel_id: str, include_videos: bool = False) -> dict[str, Any]:
        """Get channel information"""
        try:
            logger.info("Fetching channel info: %s (include_videos: %s)", channel_id, include_videos)
            
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                _ytbpy_call,
                ytb_channel.get_channel_info,
                channel_id,
                self.timeout
            )
            
            if result.get('error'):
                raise YouTubeAPIError(result['error'])
            
            # Get channel videos if requested
            if include_videos and not result.get('error'):
                videos_result = await loop.run_in_executor(
                    None,
                    _ytbpy_call,
                    ytb_channel.get_channel_videos,
                    channel_id,
                    self.settings.youtube_max_videos_per_channel,
                    self.timeout
                )
                
                if not videos_result.get('error'):
                    result['videos'] = videos_result.get('videos', [])
                    result['videos_count'] = len(result['videos'])
            
            return result
            
        except Exception as e:
            logger.error("Error fetching channel info: %s", e)
            raise YouTubeAPIError(f"Failed to get channel info: {str(e)}")
    
    async def _get_playlist_info(self, playlist_id: str) -> dict[str, Any]:
        """Get playlist information"""
        try:
            logger.info("Fetching playlist info: %s", playlist_id)
            
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                _ytbpy_call,
                ytb_playlist.get_playlist_info,
                playlist_id,
                self.timeout
            )
            
            if result.get('error'):
                raise YouTubeAPIError(result['error'])
            
            return result
            
        except Exception as e:
            logger.error("Error fetching playlist info: %s", e)
            raise YouTubeAPIError(f"Failed to get playlist info: {str(e)}")
    
    async def _search_videos(self, query: str, max_results: int = 10) -> dict[str, Any]:
        """Search for videos"""
        try:
            logger.info("Searching videos: '%s' (max: %s)", query, max_results)
            
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                _ytbpy_call,
                ytb_search.search_youtube,
                query,
                max_results,
                self.timeout
            )
            
            if result.get('error'):
                raise YouTubeAPIError(result['error'])
            
            return result
            
        except Exception as e:
            logger.error("Error searching videos: %s", e)
            raise YouTubeAPIError(f"Failed to search videos: {str(e)}")
    
    async def _get_related_videos(self, video_id: str, max_results: int = 10) -> dict[str, Any]:
        """Get related videos"""
        try:
            logger.info("Fetching related videos: %s (max: %s)", video_id, max_results)
            
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                _ytbpy_call,
                ytb_video.get_related_videos,
                video_id,
                max_results,
                self.timeout
            )
            
            # Check if result is a dict with error (for backwards compatibility)
            if isinstance(result, dict) and result.get('error'):
                raise YouTubeAPIError(result['error'])
            
            # If result is a list, wrap it in a dict
            if isinstance(result, list):
                return {
                    "video_id": video_id,
                    "results_count": len(result),
                    "results": result
                }
            
            return result
            
        except Exception as e:
            logger.error("Error fetching related videos: %s", e)
            raise YouTubeAPIError(f"Failed to get related videos: {str(e)}")
    
    async def _search_shorts(self, query: str, max_results: int = 10) -> dict[str, Any]:
        """
        Search for YouTube Shorts only
        
        Shorts are videos with duration ≤ 60 seconds
        """
        try:
            logger.info("Searching shorts: '%s' (max: %s)", query, max_results)
            
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                _ytbpy_call,
                ytb_search.search_shorts,
                query,
                max_results,
                self.timeout
            )
            
            if result.get('error'):
                raise YouTubeAPIError(result['error'])
            
            return result
            
        except Exception as e:
            logger.error("Error searching shorts: %s", e)
            raise YouTubeAPIError(f"Failed to search shorts: {str(e)}")
