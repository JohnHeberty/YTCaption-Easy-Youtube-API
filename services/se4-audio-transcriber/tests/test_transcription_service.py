"""
Testes para o serviço de transcrição.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.transcription_service import TranscriptionService, TranscriptionOrchestrator
from app.domain.models import Job, JobStatus, WhisperEngine, TranscriptionSegment, TranscriptionWord


class TestTranscriptionService:
    """Testes para TranscriptionService."""
    
    @pytest.fixture
    def service(self, mock_job_store, temp_dirs):
        """Serviço configurado para testes."""
        from app.infrastructure.whisper_engine import ModelManager
        
        # Mock do model manager
        mock_manager = MagicMock()
        mock_engine = MagicMock()
        mock_engine.is_loaded.return_value = False
        mock_manager.get_or_create_engine.return_value = mock_engine
        
        return TranscriptionService(
            job_store=mock_job_store,
            model_manager=mock_manager,
            output_dir=str(temp_dirs["output"]),
            upload_dir=str(temp_dirs["upload"]),
        )
    
    async def test_create_job_success(self, service):
        """Criação de job bem-sucedida."""
        job = await service.create_job(
            filename="test.mp3",
            language_in="pt",
            language_out="en"
        )
        
        assert job.id is not None
        assert job.language_in == "pt"
        assert job.language_out == "en"
        assert job.engine == WhisperEngine.FASTER_WHISPER
        assert job.status == JobStatus.QUEUED
    
    async def test_create_job_with_file_content(self, service, temp_dirs):
        """Criação de job com conteúdo."""
        content = b"fake audio content"
        
        job = await service.create_job(
            filename="test.mp3",
            language_in="pt",
            file_content=content
        )
        
        assert job.input_file is not None
        assert job.file_size_input == len(content)
        
        # Verifica arquivo salvo
        saved_file = Path(job.input_file)
        assert saved_file.exists()
    
    async def test_create_job_invalid_language(self, service):
        """Criação com linguagem inválida."""
        from app.core.validators import ValidationError
        
        with pytest.raises(ValidationError) as exc:
            await service.create_job(
                filename="test.mp3",
                language_in="invalid_lang"
            )
        
        assert exc.value.field == "language_in"
    
    async def test_process_job_file_not_found(self, service, sample_job):
        """Processamento com arquivo inexistente."""
        from app.shared.exceptions import AudioTranscriptionException
        
        with pytest.raises(AudioTranscriptionException) as exc:
            await service.process_job(sample_job)
        
        assert "não encontrado" in str(exc.value).lower() or "not found" in str(exc.value).lower()
    
    @patch("app.services.transcription_service.WhisperEngine")
    async def test_process_job_success(self, mock_engine_class, service, temp_dirs):
        """Processamento bem-sucedido."""
        from app.infrastructure.whisper_engine import TranscriptionResult
        
        # Cria arquivo de teste
        test_file = temp_dirs["upload"] / "test.mp3"
        test_file.write_bytes(b"fake audio")
        
        # Cria job
        job = await service.create_job(
            filename="test.mp3",
            language_in="pt"
        )
        job.input_file = str(test_file)
        
        # Mock do engine
        mock_engine = MagicMock()
        mock_engine.is_loaded.return_value = True
        mock_engine.transcribe = AsyncMock(return_value=TranscriptionResult(
            text="Hello world",
            segments=[{
                "text": "Hello world",
                "start": 0.0,
                "end": 2.5,
                "words": []
            }],
            language="en"
        ))
        
        service.model_manager.get_or_create_engine.return_value = mock_engine
        
        # Processa
        result = await service.process_job(job)
        
        assert result.status == JobStatus.COMPLETED
        assert result.transcription_text == "Hello world"
        assert result.progress == 100.0
    
    async def test_get_job_status(self, service, sample_job, mock_job_store):
        """Obtenção de status do job."""
        mock_job_store.get_job.return_value = sample_job
        
        result = await service.get_job_status("test_job_123")
        
        assert result is not None
        assert result.id == "test_job_123"
    
    async def test_delete_job(self, service, sample_job, temp_dirs, mock_job_store):
        """Remoção de job."""
        # Cria arquivo
        test_file = temp_dirs["upload"] / "test.mp3"
        test_file.write_bytes(b"content")
        sample_job.input_file = str(test_file)
        
        mock_job_store.get_job.return_value = sample_job
        
        result = await service.delete_job("test_job_123")
        
        assert result is True
        assert not test_file.exists()


class TestTranscriptionOrchestrator:
    """Testes para TranscriptionOrchestrator."""
    
    @pytest.fixture
    def orchestrator(self, mock_job_store):
        """Orquestrador configurado."""
        from app.infrastructure.whisper_engine import ModelManager
        
        mock_manager = MagicMock()
        service = TranscriptionService(
            job_store=mock_job_store,
            model_manager=mock_manager,
        )
        return TranscriptionOrchestrator(service)
    
    async def test_process_batch(self, orchestrator, mock_job_store):
        """Processamento em batch."""
        from app.domain.models import Job
        
        # Cria jobs
        jobs = [
            Job.create_new(f"test{i}.mp3", "transcribe", "pt")
            for i in range(3)
        ]
        
        # Mock do process_job para evitar processamento real
        orchestrator.service.process_job = AsyncMock(side_effect=lambda j: j)
        
        results = await orchestrator.process_batch(jobs, max_concurrent=2)
        
        assert len(results) == 3
    
    async def test_process_batch_with_failures(self, orchestrator):
        """Batch com falhas."""
        from app.domain.models import Job
        from app.shared.exceptions import AudioTranscriptionException
        
        jobs = [
            Job.create_new("test.mp3", "transcribe", "pt")
            for _ in range(2)
        ]
        
        # Primeiro falha, segundo sucede
        async def mock_process(job):
            if job.id == jobs[0].id:
                raise AudioTranscriptionException("Test error")
            return job
        
        orchestrator.service.process_job = AsyncMock(side_effect=mock_process)
        
        results = await orchestrator.process_batch(jobs)
        
        # Deve retornar apenas os que não falharam
        assert len(results) == 1
        assert results[0].id == jobs[1].id


class TestTranscriptionServiceHelpers:
    """Testes para métodos auxiliares do serviço."""
    
    def test_convert_to_srt(self):
        """Conversão para formato SRT."""
        from app.services.transcription_service import TranscriptionService
        
        segments = [
            {"text": "Hello", "start": 0.0, "end": 2.5},
            {"text": "World", "start": 3.0, "end": 5.0},
        ]
        
        service = TranscriptionService()
        srt = service._convert_to_srt(segments)
        
        assert "1" in srt
        assert "00:00:00,000 --> 00:00:02,500" in srt
        assert "Hello" in srt
        assert "2" in srt
        assert "00:00:03,000 --> 00:00:05,000" in srt
        assert "World" in srt
    
    def test_seconds_to_srt_time(self):
        """Conversão de segundos para formato SRT."""
        from app.services.transcription_service import TranscriptionService
        
        service = TranscriptionService()
        
        assert service._seconds_to_srt_time(0) == "00:00:00,000"
        assert service._seconds_to_srt_time(3661.5) == "01:01:01,500"
        assert service._seconds_to_srt_time(61.123) == "00:01:01,123"
    
    def test_convert_segments(self):
        """Conversão de segmentos."""
        from app.services.transcription_service import TranscriptionService
        
        segments = [
            {
                "text": "Hello",
                "start": 0.0,
                "end": 2.5,
                "words": [
                    {"word": "Hello", "start": 0.0, "end": 2.5, "probability": 0.95}
                ]
            }
        ]
        
        service = TranscriptionService()
        result = service._convert_segments(segments)
        
        assert len(result) == 1
        assert isinstance(result[0], TranscriptionSegment)
        assert result[0].text == "Hello"
        assert result[0].duration == 2.5
        assert len(result[0].words) == 1
        assert result[0].words[0].word == "Hello"