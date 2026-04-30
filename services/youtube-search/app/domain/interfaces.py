"""
Domain interfaces for YouTube Search service.

Defines contracts for YouTube search operations following Interface Segregation Principle.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class YouTubeSearchInterface(ABC):
    """
    Interface for YouTube search operations.

    Defines the contract that any YouTube search implementation must fulfill.
    """

    @abstractmethod
    async def get_video_info(self, video_id: str) -> Dict[str, Any]:
        """
        Get information about a specific video.

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary with video information

        Raises:
            Exception: If video not found or API error
        """
        pass

    @abstractmethod
    async def get_channel_info(
        self, channel_id: str, include_videos: bool = False
    ) -> Dict[str, Any]:
        """
        Get information about a specific channel.

        Args:
            channel_id: YouTube channel ID
            include_videos: Whether to include channel videos

        Returns:
            Dictionary with channel information

        Raises:
            Exception: If channel not found or API error
        """
        pass

    @abstractmethod
    async def get_playlist_info(self, playlist_id: str) -> Dict[str, Any]:
        """
        Get information about a specific playlist.

        Args:
            playlist_id: YouTube playlist ID

        Returns:
            Dictionary with playlist information

        Raises:
            Exception: If playlist not found or API error
        """
        pass

    @abstractmethod
    async def search_videos(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """
        Search for videos matching the query.

        Args:
            query: Search query string
            max_results: Maximum number of results (1-50)

        Returns:
            Dictionary with search results

        Raises:
            Exception: If search fails
        """
        pass

    @abstractmethod
    async def get_related_videos(
        self, video_id: str, max_results: int = 10
    ) -> Dict[str, Any]:
        """
        Get videos related to a specific video.

        Args:
            video_id: YouTube video ID
            max_results: Maximum number of results (1-50)

        Returns:
            Dictionary with related videos

        Raises:
            Exception: If request fails
        """
        pass

    @abstractmethod
    async def search_shorts(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """
        Search for YouTube Shorts matching the query.

        Args:
            query: Search query string
            max_results: Maximum number of results (1-50)

        Returns:
            Dictionary with shorts search results

        Raises:
            Exception: If search fails
        """
        pass


class JobStoreInterface(ABC):
    """
    Interface for job storage operations.

    Defines the contract that any job store implementation must fulfill.
    """

    @abstractmethod
    def save_job(self, job: Any) -> Any:
        """Save job to storage."""
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> Optional[Any]:
        """Get job by ID."""
        pass

    @abstractmethod
    def update_job(self, job: Any) -> Any:
        """Update existing job."""
        pass

    @abstractmethod
    def delete_job(self, job_id: str) -> bool:
        """Delete job by ID."""
        pass

    @abstractmethod
    def list_jobs(self, limit: int = 100) -> List[Any]:
        """List all jobs."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        pass
