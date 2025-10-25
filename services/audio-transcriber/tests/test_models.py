"""
Testes dos modelos do Audio Transcriber
"""
import pytest
from datetime import datetime
from app.models import Job, JobStatus


@pytest.mark.unit
def test_job_creation():
    """Testa criação de job"""
    job = Job.create_new(input_file="/tmp/test.mp3")
    
    assert job.id is not None
    assert job.status == JobStatus.QUEUED
    assert job.input_file == "/tmp/test.mp3"
    assert job.created_at is not None


@pytest.mark.unit
def test_job_status_transitions():
    """Testa transições de status"""
    job = Job.create_new(input_file="/tmp/test.mp3")
    
    # QUEUED -> PROCESSING
    job.status = JobStatus.PROCESSING
    job.started_at = datetime.now()
    assert job.status == JobStatus.PROCESSING
    
    # PROCESSING -> COMPLETED
    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now()
    job.output_file = "/tmp/output.txt"
    assert job.status == JobStatus.COMPLETED
    assert job.output_file is not None


@pytest.mark.unit
def test_job_serialization():
    """Testa serialização/desserialização"""
    original_job = Job.create_new(input_file="/tmp/test.mp3")
    
    # Serializa
    job_json = original_job.model_dump_json()
    assert job_json is not None
    
    # Desserializa
    restored_job = Job.model_validate_json(job_json)
    assert restored_job.id == original_job.id
    assert restored_job.status == original_job.status
