"""
Suite de testes para Audio Transcriber Service
Testes de unidade, integração e performance
"""
import pytest
import asyncio
import tempfile
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any
import json

# Imports do sistema
from app.config import AppSettings
from app.models_new import Job, JobStatus, TranscriptionRequest
from app.processor_new import TranscriptionProcessor, WhisperModelManager, AudioProcessor
from app.resource_manager import ResourceMonitor, TempFileManager, ProcessingLimiter
from app.security_validator import FileValidator, SecurityChecker
from app.observability import ObservabilityManager
from app.storage import JobStorage
from app.exceptions import TranscriptionError, AudioProcessingError, ModelLoadError


class TestConfig:
    """Configuração para testes"""
    
    @pytest.fixture
    def test_settings(self):
        """Settings para testes"""
        return AppSettings(
            debug=True,
            transcription={
                "default_model": "tiny",
                "max_file_size": 100 * 1024 * 1024,  # 100MB
                "supported_formats": [".wav", ".mp3", ".m4a"],
                "output_dir": "/tmp/test_output",
                "upload_dir": "/tmp/test_upload",
                "model_cache_dir": "/tmp/test_models"
            }
        )
    
    @pytest.fixture
    def temp_audio_file(self):
        """Cria arquivo de áudio temporário para testes"""
        
        # Cria arquivo WAV simples (1 segundo de silêncio)
        import wave
        import numpy as np
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            # Parâmetros do WAV
            sample_rate = 16000
            duration = 1.0  # 1 segundo
            
            # Gera silêncio
            samples = np.zeros(int(sample_rate * duration), dtype=np.int16)
            
            # Escreve arquivo WAV
            with wave.open(tmp_file.name, 'w') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(samples.tobytes())
            
            yield tmp_file.name
            
            # Cleanup
            try:
                os.unlink(tmp_file.name)
            except FileNotFoundError:
                pass


class TestModels:
    """Testes dos modelos de dados"""
    
    def test_job_creation(self, temp_audio_file):
        """Testa criação de job"""
        
        job = Job.create_new(
            input_file=temp_audio_file,
            language="pt",
            output_format="srt"
        )
        
        assert job.id is not None
        assert job.input_file == temp_audio_file
        assert job.language == "pt"
        assert job.output_format == "srt"
        assert job.status == JobStatus.QUEUED
        assert job.progress == 0.0
    
    def test_job_status_transitions(self, temp_audio_file):
        """Testa transições de status do job"""
        
        job = Job.create_new(input_file=temp_audio_file)
        
        # Queued -> Processing
        job.mark_as_processing("tiny", "cpu")
        assert job.status == JobStatus.PROCESSING
        assert job.started_at is not None
        assert job.whisper_model == "tiny"
        assert job.device_used == "cpu"
        
        # Processing -> Completed
        job.mark_as_completed("Test transcription", "/path/to/output.srt")
        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None
        assert job.transcription_text == "Test transcription"
        assert job.output_file == "/path/to/output.srt"
        assert job.progress == 100.0
    
    def test_job_failure_handling(self, temp_audio_file):
        """Testa tratamento de falhas"""
        
        job = Job.create_new(input_file=temp_audio_file)
        job.mark_as_processing("tiny", "cpu")
        
        # Falha
        job.mark_as_failed("Test error")
        assert job.status == JobStatus.FAILED
        assert job.error_message == "Test error"
        assert job.retry_count == 1
        assert job.can_retry is True
        
        # Múltiplas falhas
        job.mark_as_failed("Another error")
        job.mark_as_failed("Third error")
        assert job.retry_count == 3
        assert job.can_retry is False  # Atingiu max_retries
    
    def test_transcription_request_validation(self):
        """Testa validação do TranscriptionRequest"""
        
        # Request válido
        request = TranscriptionRequest(
            language="pt",
            output_format="srt",
            beam_size=5,
            temperature=0.1
        )
        
        assert request.language == "pt"
        assert request.output_format == "srt"
        
        # Language inválida
        with pytest.raises(ValueError):
            TranscriptionRequest(language="invalid")
        
        # Output format inválido
        with pytest.raises(ValueError):
            TranscriptionRequest(output_format="invalid")
        
        # Beam size fora do range
        with pytest.raises(ValueError):
            TranscriptionRequest(beam_size=25)


class TestResourceManager:
    """Testes do gerenciador de recursos"""
    
    @pytest.mark.asyncio
    async def test_resource_monitor_health_check(self):
        """Testa health check do monitor de recursos"""
        
        monitor = ResourceMonitor()
        
        health = await monitor.system_health_check()
        assert isinstance(health, bool)
        
        usage = await monitor.get_current_usage()
        assert "cpu_percent" in usage
        assert "memory_percent" in usage
        assert "disk_usage" in usage
    
    @pytest.mark.asyncio
    async def test_temp_file_manager(self):
        """Testa gerenciador de arquivos temporários"""
        
        manager = TempFileManager()
        
        # Cria arquivo temporário
        temp_file = await manager.create_temp_file(suffix='.test')
        assert os.path.exists(temp_file)
        assert temp_file.endswith('.test')
        
        # Cleanup do arquivo
        await manager.cleanup_file(temp_file)
        assert not os.path.exists(temp_file)
    
    @pytest.mark.asyncio
    async def test_processing_limiter(self):
        """Testa limitador de processamento"""
        
        limiter = ProcessingLimiter(max_concurrent=2)
        
        # Testa aquisição de slots
        async with limiter.acquire_slot():
            assert limiter.active_count == 1
            
            async with limiter.acquire_slot():
                assert limiter.active_count == 2
        
        assert limiter.active_count == 0


class TestSecurityValidator:
    """Testes do validador de segurança"""
    
    @pytest.mark.asyncio
    async def test_file_validator(self, temp_audio_file):
        """Testa validação de arquivos"""
        
        validator = FileValidator()
        
        # Lê arquivo
        with open(temp_audio_file, 'rb') as f:
            file_content = f.read()
        
        # Valida arquivo
        result = await validator.validate_audio_file(
            filename="test.wav",
            content=file_content
        )
        
        assert result.is_valid is True
        assert result.file_size > 0
        assert result.format == "wav"
    
    @pytest.mark.asyncio
    async def test_security_checker(self, temp_audio_file):
        """Testa verificações de segurança"""
        
        checker = SecurityChecker()
        
        with open(temp_audio_file, 'rb') as f:
            file_content = f.read()
        
        # Verifica arquivo
        is_safe = await checker.check_file_safety(file_content, "wav")
        assert is_safe is True
        
        # Testa detecção de formato
        detected_format = await checker.detect_audio_format(file_content)
        assert detected_format in ["wav", "audio/wav"]


class TestAudioProcessor:
    """Testes do processador de áudio"""
    
    @pytest.mark.asyncio
    async def test_audio_info_extraction(self, temp_audio_file):
        """Testa extração de informações do áudio"""
        
        processor = AudioProcessor()
        
        info = processor._get_audio_info(temp_audio_file)
        
        assert info["format"] == ".wav"
        assert info["duration"] is not None
        assert info["sample_rate"] is not None
    
    @pytest.mark.asyncio
    async def test_audio_preparation(self, temp_audio_file):
        """Testa preparação de áudio"""
        
        processor = AudioProcessor()
        
        prepared_file = await processor.prepare_audio(temp_audio_file)
        
        # Se não precisou converter, retorna o mesmo arquivo
        assert prepared_file == temp_audio_file or os.path.exists(prepared_file)


class TestWhisperModelManager:
    """Testes do gerenciador de modelos Whisper"""
    
    @pytest.mark.asyncio
    async def test_device_info(self):
        """Testa informações do device"""
        
        manager = WhisperModelManager()
        
        device_info = manager.get_device_info()
        
        assert "device" in device_info
        assert "cuda_available" in device_info
        assert device_info["device"] in ["cpu", "cuda"]
    
    @pytest.mark.asyncio
    @patch('whisper.load_model')
    async def test_model_loading(self, mock_load_model):
        """Testa carregamento de modelo (mockado)"""
        
        # Mock do modelo Whisper
        mock_model = Mock()
        mock_load_model.return_value = mock_model
        
        manager = WhisperModelManager()
        
        # Carrega modelo
        model = await manager.get_model("tiny")
        
        assert model == mock_model
        mock_load_model.assert_called_once()
        
        # Segunda chamada deve usar cache
        model2 = await manager.get_model("tiny")
        assert model2 == mock_model
        assert mock_load_model.call_count == 1  # Não chamou novamente


class TestTranscriptionProcessor:
    """Testes do processador de transcrição"""
    
    @pytest.mark.asyncio
    @patch('app.processor_new.whisper.load_model')
    async def test_transcription_processing(self, mock_load_model, temp_audio_file):
        """Testa processamento de transcrição (mockado)"""
        
        # Mock do resultado do Whisper
        mock_result = {
            "text": "Test transcription result",
            "language": "pt",
            "segments": [
                {
                    "id": 1,
                    "start": 0.0,
                    "end": 1.0,
                    "text": "Test transcription result",
                    "avg_logprob": -0.5
                }
            ]
        }
        
        mock_model = Mock()
        mock_model.transcribe.return_value = mock_result
        mock_load_model.return_value = mock_model
        
        processor = TranscriptionProcessor()
        
        # Cria job
        job = Job.create_new(
            input_file=temp_audio_file,
            language="pt",
            output_format="txt"
        )
        
        # Processa
        result = await processor.process_transcription(job)
        
        assert result.success is True
        assert result.transcription_text == "Test transcription result"
        assert job.status == JobStatus.COMPLETED
    
    def test_srt_formatting(self):
        """Testa formatação SRT"""
        
        processor = TranscriptionProcessor()
        
        segments = [
            {"id": 1, "start": 0.0, "end": 2.5, "text": "First segment"},
            {"id": 2, "start": 2.5, "end": 5.0, "text": "Second segment"}
        ]
        
        srt_content = processor._format_srt(segments)
        
        expected_lines = [
            "1",
            "00:00:00,000 --> 00:00:02,500",
            "First segment",
            "",
            "2", 
            "00:00:02,500 --> 00:00:05,000",
            "Second segment",
            ""
        ]
        
        assert srt_content == "\n".join(expected_lines)
    
    def test_time_formatting(self):
        """Testa formatação de tempo"""
        
        processor = TranscriptionProcessor()
        
        # Testa SRT
        srt_time = processor._seconds_to_srt_time(3661.250)  # 1h 1m 1.250s
        assert srt_time == "01:01:01,250"
        
        # Testa VTT
        vtt_time = processor._seconds_to_vtt_time(3661.250)
        assert vtt_time == "01:01:01.250"


class TestJobStorage:
    """Testes do sistema de armazenamento"""
    
    @pytest.mark.asyncio
    async def test_job_storage_operations(self, temp_audio_file):
        """Testa operações básicas do storage"""
        
        storage = JobStorage()
        
        # Cria job
        job = Job.create_new(input_file=temp_audio_file)
        
        # Salva job
        await storage.save_job(job)
        
        # Recupera job
        retrieved_job = await storage.get_job(job.id)
        assert retrieved_job is not None
        assert retrieved_job.id == job.id
        
        # Lista jobs
        jobs = await storage.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == job.id
        
        # Remove job
        deleted = await storage.delete_job(job.id)
        assert deleted is True
        
        # Verifica remoção
        retrieved_job = await storage.get_job(job.id)
        assert retrieved_job is None
    
    @pytest.mark.asyncio
    async def test_job_statistics(self, temp_audio_file):
        """Testa cálculo de estatísticas"""
        
        storage = JobStorage()
        
        # Cria múltiplos jobs
        jobs = []
        for i in range(5):
            job = Job.create_new(
                input_file=temp_audio_file,
                language="pt" if i % 2 == 0 else "en"
            )
            
            if i < 3:
                job.mark_as_processing("tiny", "cpu")
                job.mark_as_completed(f"Text {i}", f"/output/{i}.srt")
            elif i == 3:
                job.mark_as_failed("Test error")
            
            jobs.append(job)
            await storage.save_job(job)
        
        # Calcula estatísticas
        stats = await storage.get_stats()
        
        assert stats.total_jobs == 5
        assert stats.jobs_by_status[JobStatus.COMPLETED] == 3
        assert stats.jobs_by_status[JobStatus.FAILED] == 1
        assert stats.jobs_by_status[JobStatus.QUEUED] == 1
        assert stats.success_rate == 60.0  # 3/5 * 100


class TestObservability:
    """Testes de observabilidade"""
    
    @pytest.mark.asyncio
    async def test_observability_manager(self):
        """Testa gerenciador de observabilidade"""
        
        observability = ObservabilityManager()
        
        # Inicia observabilidade
        await observability.start()
        
        # Testa métricas
        job_id = "test_job_123"
        
        observability.start_transcription(job_id)
        time.sleep(0.1)  # Simula processamento
        observability.complete_transcription(job_id, 0.1, success=True)
        
        # Para observabilidade
        await observability.stop()
    
    @pytest.mark.asyncio
    async def test_health_checker(self):
        """Testa verificações de saúde"""
        
        observability = ObservabilityManager()
        
        health = await observability.health_checker.check_all()
        
        assert "healthy" in health
        assert "checks" in health
        assert isinstance(health["healthy"], bool)


class TestPerformance:
    """Testes de performance"""
    
    @pytest.mark.asyncio
    async def test_concurrent_jobs(self, temp_audio_file):
        """Testa processamento concorrente"""
        
        storage = JobStorage()
        
        # Cria múltiplos jobs
        jobs = []
        for i in range(10):
            job = Job.create_new(input_file=temp_audio_file)
            jobs.append(job)
            await storage.save_job(job)
        
        # Testa recuperação concorrente
        async def get_job_async(job_id):
            return await storage.get_job(job_id)
        
        start_time = time.time()
        
        tasks = [get_job_async(job.id) for job in jobs]
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        
        assert len(results) == 10
        assert all(result is not None for result in results)
        
        # Deve ser rápido (menos de 1 segundo)
        assert end_time - start_time < 1.0
    
    @pytest.mark.asyncio
    async def test_memory_usage(self, temp_audio_file):
        """Testa uso de memória com muitos jobs"""
        
        import psutil
        import gc
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        storage = JobStorage()
        
        # Cria muitos jobs
        for i in range(1000):
            job = Job.create_new(input_file=temp_audio_file)
            await storage.save_job(job)
        
        # Força garbage collection
        gc.collect()
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Verifica que o aumento de memória é razoável (< 100MB)
        assert memory_increase < 100 * 1024 * 1024


class TestErrorHandling:
    """Testes de tratamento de erros"""
    
    @pytest.mark.asyncio
    async def test_file_not_found_error(self):
        """Testa erro de arquivo não encontrado"""
        
        processor = AudioProcessor()
        
        with pytest.raises(AudioProcessingError):
            await processor.prepare_audio("/nonexistent/file.wav")
    
    @pytest.mark.asyncio
    async def test_invalid_audio_file(self):
        """Testa arquivo de áudio inválido"""
        
        validator = FileValidator()
        
        # Arquivo de texto como áudio
        text_content = b"This is not an audio file"
        
        result = await validator.validate_audio_file("test.wav", text_content)
        
        assert result.is_valid is False
        assert result.error is not None
    
    @pytest.mark.asyncio
    @patch('app.processor_new.whisper.load_model')
    async def test_model_loading_failure(self, mock_load_model):
        """Testa falha no carregamento do modelo"""
        
        mock_load_model.side_effect = Exception("Model loading failed")
        
        manager = WhisperModelManager()
        
        with pytest.raises(ModelLoadError):
            await manager.get_model("tiny")


class TestIntegration:
    """Testes de integração"""
    
    @pytest.mark.asyncio
    @patch('app.processor_new.whisper.load_model')
    async def test_full_transcription_workflow(self, mock_load_model, temp_audio_file):
        """Testa workflow completo de transcrição"""
        
        # Mock do Whisper
        mock_result = {
            "text": "Complete transcription test",
            "language": "en",
            "segments": []
        }
        
        mock_model = Mock()
        mock_model.transcribe.return_value = mock_result
        mock_load_model.return_value = mock_model
        
        # Componentes
        storage = JobStorage()
        processor = TranscriptionProcessor()
        
        # Cria job
        job = Job.create_new(
            input_file=temp_audio_file,
            language="auto",
            output_format="srt"
        )
        
        # Salva job
        await storage.save_job(job)
        
        # Processa
        result = await processor.process_transcription(job)
        
        # Verifica resultado
        assert result.success is True
        assert job.status == JobStatus.COMPLETED
        assert job.transcription_text == "Complete transcription test"
        
        # Atualiza no storage
        await storage.save_job(job)
        
        # Recupera job atualizado
        updated_job = await storage.get_job(job.id)
        assert updated_job.status == JobStatus.COMPLETED


# Configuração do pytest
def pytest_configure(config):
    """Configuração do pytest"""
    
    # Markers personalizados
    config.addinivalue_line(
        "markers", "slow: marca testes lentos"
    )
    config.addinivalue_line(
        "markers", "integration: marca testes de integração"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])