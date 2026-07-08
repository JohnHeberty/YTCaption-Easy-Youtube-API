"""
Unit tests for models
"""
import pytest
from datetime import datetime, timedelta
from app.domain.models import YouTubeSearchJob, JobStatus, SearchType, SearchRequest


def test_job_create_new_video_info():
    """Test creating new video info job"""
    job = YouTubeSearchJob.create_new(
        search_type=SearchType.VIDEO_INFO,
        video_id="dQw4w9WgXcQ",
    )
    
    assert job.id is not None
    assert len(job.id) > 0
    assert job.search_type == SearchType.VIDEO_INFO
    assert job.video_id == "dQw4w9WgXcQ"
    assert job.status == JobStatus.QUEUED
    assert job.progress == 0.0
    assert job.result is None
    assert job.error_message is None


def test_job_create_new_channel_info():
    """Test creating new channel info job"""
    job = YouTubeSearchJob.create_new(
        search_type=SearchType.CHANNEL_INFO,
        channel_id="UCuAXFkgsw1L7xaCfnd5JJOw",
        include_videos=True,
    )
    
    assert job.channel_id == "UCuAXFkgsw1L7xaCfnd5JJOw"
    assert job.include_videos is True
    assert job.search_type == SearchType.CHANNEL_INFO


def test_job_create_new_video_search():
    """Test creating new video search job"""
    job = YouTubeSearchJob.create_new(
        search_type=SearchType.VIDEO,
        query="python tutorial",
        max_results=20,
    )
    
    assert job.query == "python tutorial"
    assert job.max_results == 20
    assert job.search_type == SearchType.VIDEO


def test_job_unique_id_same_params():
    """Test that same parameters generate same job ID (caching)"""
    job1 = YouTubeSearchJob.create_new(
        search_type=SearchType.VIDEO_INFO,
        video_id="dQw4w9WgXcQ"
    )
    
    job2 = YouTubeSearchJob.create_new(
        search_type=SearchType.VIDEO_INFO,
        video_id="dQw4w9WgXcQ"
    )
    
    assert job1.id == job2.id


def test_job_different_id_different_params():
    """Test that different parameters generate different job IDs"""
    job1 = YouTubeSearchJob.create_new(
        search_type=SearchType.VIDEO_INFO,
        video_id="dQw4w9WgXcQ"
    )
    
    job2 = YouTubeSearchJob.create_new(
        search_type=SearchType.VIDEO_INFO,
        video_id="abc123def456"
    )
    
    assert job1.id != job2.id


def test_job_expires_at():
    """Test job expiration field"""
    job = YouTubeSearchJob.create_new(
        search_type=SearchType.VIDEO_INFO,
        video_id="dQw4w9WgXcQ",
    )
    
    # expires_at is None by default
    assert job.expires_at is None
    
    # Set expiration manually
    job.expires_at = datetime.now() + timedelta(hours=1)
    assert job.expires_at is not None
    assert job.expires_at > datetime.now()


def test_search_request_validation():
    """Test search request model validation"""
    request = SearchRequest(
        search_type=SearchType.VIDEO,
        query="python",
        max_results=10
    )
    
    assert request.query == "python"
    assert request.max_results == 10


def test_search_request_max_results_default():
    """Test search request default max_results"""
    request = SearchRequest(
        search_type=SearchType.VIDEO,
        query="python"
    )
    
    assert request.max_results == 10


def test_job_status_enum():
    """Test job status enum values"""
    assert JobStatus.QUEUED.value == "queued"
    assert JobStatus.PROCESSING.value == "processing"
    assert JobStatus.COMPLETED.value == "completed"
    assert JobStatus.FAILED.value == "failed"


def test_search_type_enum():
    """Test search type enum values"""
    assert SearchType.VIDEO.value == "video"
    assert SearchType.CHANNEL_INFO.value == "channel_info"
    assert SearchType.VIDEO_INFO.value == "video_info"
    assert SearchType.PLAYLIST_INFO.value == "playlist_info"
    assert SearchType.RELATED_VIDEOS.value == "related_videos"
