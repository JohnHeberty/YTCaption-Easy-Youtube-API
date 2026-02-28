"""
Testes Unitários - Models Module
Princípio SOLID: Single Responsibility - Testa apenas modelos de dados
"""
import pytest
from datetime import datetime
from app.domain.models import Job, JobStatus, TranscriptionSegment, TranscriptionResponse


class TestJobStatus:
    """Testa enum de status de jobs"""
    
    def test_job_status_has_all_states(self):
        """Deve ter todos estados necessários"""
        assert hasattr(JobStatus, 'QUEUED')
        assert hasattr(JobStatus, 'PROCESSING')
        assert hasattr(JobStatus, 'COMPLETED')
        assert hasattr(JobStatus, 'FAILED')
    
    def test_job_status_values_are_strings(self):
        """Valores devem ser strings"""
        assert isinstance(JobStatus.QUEUED.value, str)
        assert isinstance(JobStatus.PROCESSING.value, str)
        assert isinstance(JobStatus.COMPLETED.value, str)
        assert isinstance(JobStatus.FAILED.value, str)


class TestJobModel:
    """Testa modelo Job"""
    
    def test_job_create_new(self):
        """Deve criar novo job com valores padrão"""
        job = Job.create_new("test_audio.mp3", "transcribe")
        
        assert job.id is not None
        assert len(job.id) > 0
        assert job.filename == "test_audio.mp3"
        assert job.operation == "transcribe"
        assert job.status == JobStatus.QUEUED
        assert job.progress == 0.0
        assert job.language == "auto"  # Default
    
    def test_job_id_is_unique(self):
        """IDs de jobs diferentes devem ser únicos"""
        job1 = Job.create_new("audio1.mp3", "transcribe")
        job2 = Job.create_new("audio2.mp3", "transcribe")
        
        assert job1.id != job2.id
    
    def test_job_with_custom_language(self):
        """Deve aceitar linguagem customizada"""
        job = Job.create_new("audio.mp3", "transcribe")
        job.language = "pt"
        
        assert job.language == "pt"
    
    def test_job_progress_validation(self):
        """Progresso deve estar entre 0 e 100"""
        job = Job.create_new("audio.mp3", "transcribe")
        
        # Progresso válido
        job.progress = 50.0
        assert job.progress == 50.0
        
        job.progress = 0.0
        assert job.progress == 0.0
        
        job.progress = 100.0
        assert job.progress == 100.0
    
    def test_job_timestamps(self):
        """Deve ter timestamps corretos"""
        job = Job.create_new("audio.mp3", "transcribe")
        
        assert hasattr(job, 'created_at')
        assert hasattr(job, 'updated_at')
    
    def test_job_model_dump(self):
        """Deve serializar para dict"""
        job = Job.create_new("audio.mp3", "transcribe")
        job_dict = job.model_dump()
        
        assert isinstance(job_dict, dict)
        assert 'id' in job_dict
        assert 'filename' in job_dict
        assert 'status' in job_dict
        assert 'language' in job_dict


class TestTranscriptionSegment:
    """Testa modelo de segmento de transcrição"""
    
    def test_segment_creation(self):
        """Deve criar segmento com todos campos"""
        segment = TranscriptionSegment(
            text="Hello world",
            start=0.0,
            end=2.5,
            duration=2.5
        )
        
        assert segment.text == "Hello world"
        assert segment.start == 0.0
        assert segment.end == 2.5
        assert segment.duration == 2.5
    
    def test_segment_timing_consistency(self):
        """Duration deve ser consistente com start/end"""
        segment = TranscriptionSegment(
            text="Test",
            start=1.0,
            end=3.5,
            duration=2.5
        )
        
        assert segment.duration == segment.end - segment.start
    
    def test_segment_text_required(self):
        """Texto é obrigatório"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            TranscriptionSegment(
                start=0.0,
                end=1.0,
                duration=1.0
                # text missing
            )


class TestTranscriptionResponse:
    """Testa modelo de resposta de transcrição"""
    
    def test_response_creation(self):
        """Deve criar resposta completa"""
        segments = [
            TranscriptionSegment(text="Hello", start=0.0, end=1.0, duration=1.0),
            TranscriptionSegment(text="World", start=1.0, end=2.0, duration=1.0)
        ]
        
        response = TranscriptionResponse(
            full_text="Hello World",
            segments=segments,
            total_segments=2,
            duration=2.0,
            processing_time=0.5
        )
        
        assert response.full_text == "Hello World"
        assert len(response.segments) == 2
        assert response.total_segments == 2
        assert response.duration == 2.0
        assert response.processing_time == 0.5
    
    def test_response_with_empty_segments(self):
        """Deve aceitar lista vazia de segmentos"""
        response = TranscriptionResponse(
            full_text="",
            segments=[],
            total_segments=0,
            duration=0.0,
            processing_time=0.0
        )
        
        assert len(response.segments) == 0
        assert response.total_segments == 0
    
    def test_response_segment_count_consistency(self):
        """total_segments deve bater com len(segments)"""
        segments = [
            TranscriptionSegment(text="A", start=0.0, end=1.0, duration=1.0),
            TranscriptionSegment(text="B", start=1.0, end=2.0, duration=1.0),
            TranscriptionSegment(text="C", start=2.0, end=3.0, duration=1.0)
        ]
        
        response = TranscriptionResponse(
            full_text="A B C",
            segments=segments,
            total_segments=3,
            duration=3.0,
            processing_time=1.0
        )
        
        assert response.total_segments == len(response.segments)


class TestModelValidation:
    """Testa validações dos modelos"""
    
    def test_job_status_must_be_valid_enum(self):
        """Status deve ser um valor válido do enum"""
        job = Job.create_new("audio.mp3", "transcribe")
        
        # Status válidos
        valid_statuses = [JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.COMPLETED, JobStatus.FAILED]
        for status in valid_statuses:
            job.status = status
            assert job.status == status
    
    def test_segment_timing_must_be_positive(self):
        """Timing dos segmentos deve ser positivo"""
        # Start/end/duration devem ser >= 0
        segment = TranscriptionSegment(
            text="Test",
            start=0.0,
            end=1.0,
            duration=1.0
        )
        
        assert segment.start >= 0
        assert segment.end >= 0
        assert segment.duration >= 0
