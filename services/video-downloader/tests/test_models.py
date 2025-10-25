"""
Testes dos modelos do Video Downloader
"""
import pytest
from app.models import Job, JobStatus


@pytest.mark.unit
def test_job_creation():
    """Testa criação de job"""
    job = Job.create_new(
        url="https://youtube.com/watch?v=test123",
        quality="best"
    )
    
    assert job.id is not None
    assert job.status == JobStatus.QUEUED
    assert job.url == "https://youtube.com/watch?v=test123"
    assert job.quality == "best"


@pytest.mark.unit
def test_job_serialization():
    """Testa serialização/desserialização"""
    original_job = Job.create_new(
        url="https://youtube.com/watch?v=test123",
        quality="720p"
    )
    
    # Serializa
    job_json = original_job.model_dump_json()
    assert job_json is not None
    
    # Desserializa
    restored_job = Job.model_validate_json(job_json)
    assert restored_job.id == original_job.id
    assert restored_job.url == original_job.url
