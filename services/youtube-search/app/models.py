from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import hashlib


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SearchType(str, Enum):
    VIDEO = "video"
    CHANNEL = "channel"
    PLAYLIST = "playlist"
    VIDEO_INFO = "video_info"
    CHANNEL_INFO = "channel_info"
    PLAYLIST_INFO = "playlist_info"
    RELATED_VIDEOS = "related_videos"
    SHORTS = "shorts"


class VideoInfo(BaseModel):
    """Video information model"""
    video_id: str
    title: Optional[str] = None
    thumbnails: Optional[Dict[str, Any]] = None
    url: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[str] = None
    duration_seconds: Optional[int] = None
    views_count: Optional[int] = None
    view_count_text: Optional[str] = None
    likes_count: Optional[int] = None
    publish_date: Optional[int] = None
    publish_date_text: Optional[str] = None
    upload_date: Optional[int] = None
    upload_date_text: Optional[str] = None
    published_time: Optional[str] = None
    approximate_upload_date: Optional[str] = None
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    channel_url: Optional[str] = None
    author_name: Optional[str] = None
    is_live: Optional[bool] = False
    is_private: Optional[bool] = False
    is_short: Optional[bool] = False
    category: Optional[str] = None
    keywords: Optional[List[str]] = None
    badges: Optional[List[str]] = None


class ChannelInfo(BaseModel):
    """Channel information model"""
    channel_id: str
    title: str
    channel_url: Optional[str] = None
    description: Optional[str] = None
    description_snippet: Optional[str] = None
    handle: Optional[str] = None
    handle_name: Optional[str] = None
    vanity_url: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    subscriber_count_text: Optional[str] = None
    subscriber_count_approximate: Optional[int] = None
    video_count: Optional[int] = None
    view_count: Optional[int] = None
    joined_date: Optional[str] = None
    location: Optional[str] = None
    videos_count: Optional[int] = None


class PlaylistInfo(BaseModel):
    """Playlist information model"""
    playlist_id: str
    title: str
    description: Optional[str] = None
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    video_count: Optional[int] = None
    thumbnails: Optional[Dict[str, Any]] = None
    videos: Optional[List[VideoInfo]] = None


class SearchRequest(BaseModel):
    """Request for YouTube search operations"""
    query: Optional[str] = None
    video_id: Optional[str] = None
    channel_id: Optional[str] = None
    playlist_id: Optional[str] = None
    search_type: SearchType = SearchType.VIDEO
    max_results: int = Field(default=10, ge=1, le=50)
    include_videos: bool = False  # For channel info


class Job(BaseModel):
    id: str
    search_type: SearchType
    query: Optional[str] = None
    video_id: Optional[str] = None
    channel_id: Optional[str] = None
    playlist_id: Optional[str] = None
    max_results: int = 10
    include_videos: bool = False
    status: JobStatus
    result: Optional[Dict[str, Any]] = None
    received_at: datetime  # Quando foi recebido
    created_at: datetime   # Alias para received_at (compatibilidade)
    started_at: Optional[datetime] = None     # Quando começou a processar
    completed_at: Optional[datetime] = None   # Quando finalizou
    error_message: Optional[str] = None
    expires_at: datetime
    progress: float = 0.0  # Progress from 0.0 to 100.0
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at
    
    @classmethod
    def create_new(
        cls,
        search_type: SearchType,
        query: Optional[str] = None,
        video_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        playlist_id: Optional[str] = None,
        max_results: int = 10,
        include_videos: bool = False,
        cache_ttl_hours: int = 24
    ) -> "Job":
        """Creates a new job with unique ID based on search parameters"""
        
        # Create unique ID based on search parameters
        id_parts = [search_type.value]
        if query:
            id_parts.append(f"q:{query}")
        if video_id:
            id_parts.append(f"v:{video_id}")
        if channel_id:
            id_parts.append(f"c:{channel_id}")
        if playlist_id:
            id_parts.append(f"p:{playlist_id}")
        id_parts.append(f"max:{max_results}")
        if include_videos:
            id_parts.append("inc_videos")
        
        id_string = "|".join(id_parts)
        job_id = hashlib.sha256(id_string.encode()).hexdigest()[:16]
        
        now = datetime.now()
        return cls(
            id=job_id,
            search_type=search_type,
            query=query,
            video_id=video_id,
            channel_id=channel_id,
            playlist_id=playlist_id,
            max_results=max_results,
            include_videos=include_videos,
            status=JobStatus.QUEUED,
            received_at=now,
            created_at=now,
            expires_at=now + timedelta(hours=cache_ttl_hours)
        )


class JobListResponse(BaseModel):
    """Response for job list"""
    jobs: List[Job]
    total: int
