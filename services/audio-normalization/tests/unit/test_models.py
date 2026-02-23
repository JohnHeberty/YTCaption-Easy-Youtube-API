"""
Testes unitários para os modelos de dados do audio-normalization
"""
import pytest
from datetime import datetime
from app.models import Job, JobStatus


class TestJobStatus:
    """Testes para enum JobStatus"""
    
    def test_job_status_values(self):
        """JobStatus deve ter valores esperados"""
        assert hasattr(JobStatus, "QUEUED")
        assert hasattr(JobStatus, "PROCESSING")
        assert hasattr(JobStatus, "COMPLETED")
        assert hasattr(JobStatus, "FAILED")
    
    def test_job_status_string_values(self):
        """Valores do enum devem ser strings"""
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.PROCESSING.value == "processing"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"


class TestJobModel:
    """Testes para o modelo Job"""
    
    def test_create_new_job(self):
        """Deve criar job com ID único"""
        job = Job.create_new(
            input_file="test.mp4",
            remove_noise=True,
            convert_to_mono=True,
            sample_rate_16k=True
        )
        
        assert job.id is not None
        assert len(job.id) > 0
        assert job.input_file == "test.mp4"
        assert job.status == JobStatus.QUEUED
    
    def test_job_id_uniqueness(self):
        """IDs de jobs devem ser únicos"""
        job1 = Job.create_new(input_file="test1.mp4")
        job2 = Job.create_new(input_file="test2.mp4")
        
        assert job1.id != job2.id
    
    def test_job_default_values(self):
        """Job deve ter valores padrão corretos"""
        job = Job.create_new(input_file="test.mp4")
        
        assert job.status == JobStatus.QUEUED
        assert isinstance(job.created_at, datetime)
        assert job.progress == 0.0
        assert job.error_message is None
    
    def test_job_parameters_stored(self):
        """Parâmetros de normalização devem ser armazenados"""
        job = Job.create_new(
            input_file="test.mp4",
            remove_noise=True,
            convert_to_mono=False,
            sample_rate_16k=True
        )
        
        assert job.remove_noise is True
        assert job.convert_to_mono is False
        assert job.sample_rate_16k is True


class TestJobStatusTransitions:
    """Testes para transições de status do job"""
    
    def test_job_starts_as_queued(self):
        """Novo job deve começar como QUEUED"""
        job = Job.create_new(input_file="test.mp4")
        assert job.status == JobStatus.QUEUED
    
    def test_update_status_to_processing(self):
        """Deve permitir atualizar para PROCESSING"""
        job = Job.create_new(input_file="test.mp4")
        job.status = JobStatus.PROCESSING
        assert job.status == JobStatus.PROCESSING
    
    def test_update_status_to_completed(self):
        """Deve permitir atualizar para COMPLETED"""
        job = Job.create_new(input_file="test.mp4")
        job.status = JobStatus.COMPLETED
        job.output_file = "output.wav"
        
        assert job.status == JobStatus.COMPLETED
        assert job.output_file == "output.wav"
    
    def test_update_status_to_failed(self):
        """Deve permitir atualizar para FAILED com mensagem de erro"""
        job = Job.create_new(input_file="test.mp4")
        job.status = JobStatus.FAILED
        job.error_message = "File not found"
        
        assert job.status == JobStatus.FAILED
        assert job.error_message == "File not found"


class TestJobProgress:
    """Testes para progresso do job"""
    
    def test_initial_progress_is_zero(self):
        """Progresso inicial deve ser 0"""
        job = Job.create_new(input_file="test.mp4")
        assert job.progress == 0.0
    
    def test_update_progress(self):
        """Deve permitir atualizar progresso"""
        job = Job.create_new(input_file="test.mp4")
        job.progress = 50.0
        assert job.progress == 50.0
    
    def test_progress_validation(self):
        """Progresso deve estar entre 0 e 100"""
        job = Job.create_new(input_file="test.mp4")
        
        # Valores válidos
        job.progress = 0.0
        assert job.progress == 0.0
        
        job.progress = 100.0
        assert job.progress == 100.0
        
        job.progress = 50.5
        assert job.progress == 50.5


class TestModelSerialization:
    """Testes para serialização dos modelos"""
    
    def test_job_to_dict(self):
        """Job deve poder ser convertido para dict"""
        job = Job.create_new(input_file="test.mp4")
        job_dict = job.model_dump()
        
        assert isinstance(job_dict, dict)
        assert job_dict["input_file"] == "test.mp4"
        assert job_dict["status"] == JobStatus.QUEUED.value
    
    def test_job_from_dict(self):
        """Job deve poder ser criado a partir de dict"""
        job_data = {
            "id": "test123",
            "input_file": "test.mp4",
            "status": JobStatus.QUEUED,
            "remove_noise": True,
            "convert_to_mono": True,
            "sample_rate_16k": True,
            "progress": 0.0
        }
        
        job = Job(**job_data)
        assert job.id == "test123"
        assert job.input_file == "test.mp4"
