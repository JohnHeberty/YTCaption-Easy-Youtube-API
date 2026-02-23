"""
Testes unitários para modelos de dados
"""
import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from app.models import Job, JobStatus, AudioNormalizationRequest


class TestJob:
    """Testes para o modelo Job"""
    
    def test_job_creation(self, temp_dir):
        """Testa criação básica de job"""
        # Cria arquivo temporário
        test_file = temp_dir / "test.mp3"
        test_file.write_text("dummy audio content")
        
        job = Job.create_new(
            input_file=str(test_file),
            remove_noise=True,
            normalize_volume=True
        )
        
        assert job.id is not None
        assert job.status == JobStatus.QUEUED
        assert job.remove_noise is True
        assert job.normalize_volume is True
        assert job.convert_to_mono is True  # Padrão
        assert job.created_at is not None
        assert job.expires_at > job.created_at
        assert not job.is_expired
    
    def test_job_id_generation(self, temp_dir):
        """Testa geração consistente de ID baseado no hash"""
        test_file = temp_dir / "test.mp3"
        test_file.write_bytes(b"consistent content for testing")
        
        # Cria dois jobs com mesmo arquivo e operações
        job1 = Job.create_new(
            input_file=str(test_file),
            remove_noise=True,
            normalize_volume=True
        )
        
        job2 = Job.create_new(
            input_file=str(test_file),
            remove_noise=True,
            normalize_volume=True
        )
        
        # IDs devem ser iguais (cache behavior)
        assert job1.id == job2.id
    
    def test_job_id_different_operations(self, temp_dir):
        """Testa que operações diferentes geram IDs diferentes"""
        test_file = temp_dir / "test.mp3"
        test_file.write_bytes(b"consistent content")
        
        job1 = Job.create_new(
            input_file=str(test_file),
            remove_noise=True,
            normalize_volume=False
        )
        
        job2 = Job.create_new(
            input_file=str(test_file),
            remove_noise=False,
            normalize_volume=True
        )
        
        assert job1.id != job2.id
    
    def test_job_expiration(self):
        """Testa lógica de expiração"""
        # Job já expirado
        expired_job = Job(
            id="test-expired",
            input_file="/tmp/test.mp3",
            status=JobStatus.COMPLETED,
            isolate_vocals=False,
            remove_noise=True,
            normalize_volume=True,
            convert_to_mono=True,
            apply_highpass_filter=True,
            set_sample_rate_16k=True,
            created_at=datetime.now() - timedelta(hours=25),
            expires_at=datetime.now() - timedelta(hours=1)
        )
        
        assert expired_job.is_expired
        
        # Job ainda válido
        valid_job = Job(
            id="test-valid",
            input_file="/tmp/test.mp3",
            status=JobStatus.QUEUED,
            isolate_vocals=False,
            remove_noise=True,
            normalize_volume=True,
            convert_to_mono=True,
            apply_highpass_filter=True,
            set_sample_rate_16k=True,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1)
        )
        
        assert not valid_job.is_expired
    
    def test_job_serialization(self):
        """Testa se job pode ser serializado/deserializado"""
        job = Job(
            id="test-serialization",
            input_file="/tmp/test.mp3",
            status=JobStatus.PROCESSING,
            isolate_vocals=True,
            remove_noise=True,
            normalize_volume=True,
            convert_to_mono=False,
            apply_highpass_filter=True,
            set_sample_rate_16k=True,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24),
            progress=50.0,
            file_size_input=1024000
        )
        
        # Serialização
        job_dict = job.model_dump()
        
        # Verificações básicas
        assert job_dict["id"] == "test-serialization"
        assert job_dict["status"] == "processing"
        assert job_dict["progress"] == 50.0
        assert job_dict["isolate_vocals"] is True
        assert job_dict["convert_to_mono"] is False
        
        # Deserialização
        reconstructed = Job(**job_dict)
        assert reconstructed.id == job.id
        assert reconstructed.status == job.status
        assert reconstructed.progress == job.progress


class TestAudioNormalizationRequest:
    """Testes para modelo de request"""
    
    def test_request_validation(self):
        """Testa validação de request"""
        # Request válido
        request = AudioNormalizationRequest(
            audio_file_path="/tmp/test.wav",
            remove_noise=True,
            normalize_volume=True
        )
        
        assert request.audio_file_path == "/tmp/test.wav"
        assert request.remove_noise is True
        assert request.normalize_volume is True
        assert request.isolate_vocals is False  # Padrão
        assert request.convert_to_mono is True  # Padrão
    
    def test_request_defaults(self):
        """Testa valores padrão do request"""
        request = AudioNormalizationRequest(
            audio_file_path="/tmp/test.wav"
        )
        
        assert request.isolate_vocals is False
        assert request.remove_noise is True
        assert request.normalize_volume is True
        assert request.convert_to_mono is True
        assert request.apply_highpass_filter is True


class TestJobStatuses:
    """Testes para estados de job"""
    
    def test_job_status_enum(self):
        """Testa enum de status"""
        assert JobStatus.QUEUED == "queued"
        assert JobStatus.PROCESSING == "processing"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"
    
    def test_job_status_transitions(self):
        """Testa transições válidas de status"""
        job = Job(
            id="test-status",
            input_file="/tmp/test.mp3",
            status=JobStatus.QUEUED,
            isolate_vocals=False,
            remove_noise=True,
            normalize_volume=True,
            convert_to_mono=True,
            apply_highpass_filter=True,
            set_sample_rate_16k=True,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24)
        )
        
        # Transição normal: QUEUED -> PROCESSING
        job.status = JobStatus.PROCESSING
        assert job.status == JobStatus.PROCESSING
        
        # Transição normal: PROCESSING -> COMPLETED
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now()
        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None
        
        # Pode falhar de qualquer estado
        job.status = JobStatus.FAILED
        job.error_message = "Test error"
        assert job.status == JobStatus.FAILED
        assert job.error_message == "Test error"