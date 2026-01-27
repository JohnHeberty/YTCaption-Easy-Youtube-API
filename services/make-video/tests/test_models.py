"""
Test Models
"""

import pytest
from datetime import datetime
from app.models import Job, JobStatus, CreateVideoRequest, JobResult, ShortInfo


def test_job_creation():
    """Test Job model creation"""
    job = Job(
        job_id="test-123",
        status=JobStatus.QUEUED,
        query="test query",
        max_shorts=10,
        subtitle_language="pt",
        subtitle_style="static",
        aspect_ratio="9:16",
        crop_position="center"
    )
    
    assert job.job_id == "test-123"
    assert job.status == JobStatus.QUEUED
    assert job.progress == 0.0
    assert job.query == "test query"
    assert job.aspect_ratio == "9:16"
    assert job.crop_position == "center"


def test_create_video_request():
    """Test CreateVideoRequest validation"""
    request = CreateVideoRequest(
        query="fitness motivation",
        max_shorts=15,
        subtitle_language="en",
        subtitle_style="dynamic",
        aspect_ratio="16:9",
        crop_position="top"
    )
    
    assert request.query == "fitness motivation"
    assert request.max_shorts == 15
    assert request.aspect_ratio == "16:9"
    assert request.crop_position == "top"


def test_job_status_enum():
    """Test JobStatus enum values"""
    assert JobStatus.QUEUED.value == "queued"
    assert JobStatus.ANALYZING_AUDIO.value == "analyzing_audio"
    assert JobStatus.COMPLETED.value == "completed"
    assert JobStatus.FAILED.value == "failed"


def test_job_result():
    """Test JobResult model"""
    result = JobResult(
        video_url="/download/test-123",
        video_file="test-123_final.mp4",
        file_size=10485760,
        file_size_mb=10.0,
        duration=60.5,
        resolution="1080x1920",
        aspect_ratio="9:16",
        fps=30,
        shorts_used=5,
        shorts_list=[],
        subtitle_segments=50,
        processing_time=120.5
    )
    
    assert result.file_size_mb == 10.0
    assert result.duration == 60.5
    assert result.aspect_ratio == "9:16"
    assert result.shorts_used == 5
