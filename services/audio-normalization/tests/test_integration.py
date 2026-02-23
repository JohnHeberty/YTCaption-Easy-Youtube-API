"""
Testes de integração para o sistema completo
"""
import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from fastapi import UploadFile

from app.models import Job, JobStatus
from app.redis_store_new import RedisJobStore
from app.processor_new import AudioProcessor


class TestRedisJobStore:
    """Testes de integração para Redis Job Store"""
    
    @pytest.fixture
    async def real_redis_store(self):
        """Store com Redis real (usar apenas em testes de integração)"""
        try:
            store = RedisJobStore("redis://localhost:6379/15")
            yield store
            
            # Cleanup
            await store.stop_cleanup_task()
        except Exception:
            pytest.skip("Redis não disponível para testes de integração")
    
    async def test_job_save_and_retrieve(self, job_store, sample_job):
        """Testa salvamento e recuperação de job"""
        # Salva job
        saved_job = job_store.save_job(sample_job)
        assert saved_job.id == sample_job.id
        
        # Recupera job
        retrieved_job = job_store.get_job(sample_job.id)
        assert retrieved_job is not None
        assert retrieved_job.id == sample_job.id
        assert retrieved_job.status == sample_job.status
        assert retrieved_job.remove_noise == sample_job.remove_noise
    
    def test_job_not_found(self, job_store):
        """Testa job não encontrado"""
        result = job_store.get_job("non-existent-job")
        assert result is None
    
    async def test_job_update(self, job_store, sample_job):
        """Testa atualização de job"""
        # Salva job inicial
        job_store.save_job(sample_job)
        
        # Atualiza status
        sample_job.status = JobStatus.PROCESSING
        sample_job.progress = 50.0
        updated_job = job_store.update_job(sample_job)
        
        # Verifica atualização
        retrieved_job = job_store.get_job(sample_job.id)
        assert retrieved_job.status == JobStatus.PROCESSING
        assert retrieved_job.progress == 50.0
    
    def test_job_deletion(self, job_store, sample_job):
        """Testa deleção de job"""
        # Salva job
        job_store.save_job(sample_job)
        assert job_store.get_job(sample_job.id) is not None
        
        # Deleta job
        deleted = job_store.delete_job(sample_job.id)
        assert deleted is True
        
        # Verifica se foi deletado
        assert job_store.get_job(sample_job.id) is None
    
    def test_list_jobs(self, job_store):
        """Testa listagem de jobs"""
        # Cria múltiplos jobs
        jobs = []
        for i in range(3):
            job = Job.create_new(
                input_file=f"/tmp/test{i}.mp3",
                remove_noise=True,
                normalize_volume=i % 2 == 0  # Varia operações
            )
            job_store.save_job(job)
            jobs.append(job)
        
        # Lista jobs
        job_list = job_store.list_jobs(limit=10)
        
        assert len(job_list) >= 3
        # Verifica se está ordenado por data de criação (mais recente primeiro)
        if len(job_list) > 1:
            assert job_list[0].created_at >= job_list[1].created_at
    
    def test_job_stats(self, job_store, sample_job):
        """Testa estatísticas de jobs"""
        # Salva job
        job_store.save_job(sample_job)
        
        # Obtém stats
        stats = job_store.get_stats()
        
        assert "total_jobs" in stats
        assert "by_status" in stats
        assert "cache_config" in stats
        assert stats["total_jobs"] >= 1
    
    async def test_cleanup_expired(self, job_store):
        """Testa limpeza de jobs expirados"""
        # Cria job já expirado
        expired_job = Job(
            id="expired-test",
            input_file="/tmp/expired.mp3",
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
        
        job_store.save_job(expired_job)
        
        # Executa cleanup
        removed_count = await job_store.cleanup_expired()
        
        # Job expirado deve ter sido removido
        assert removed_count >= 1
        assert job_store.get_job(expired_job.id) is None


class TestAudioProcessor:
    """Testes de integração para processador de áudio"""
    
    def test_processor_initialization(self, audio_processor):
        """Testa inicialização do processador"""
        assert audio_processor.settings is not None
        assert audio_processor.temp_manager is not None
        assert audio_processor.processing_limiter is not None
        assert audio_processor.output_dir.exists()
    
    @patch('app.processor_new.AudioSegment.from_file')
    @patch('app.processor_new.AudioSegment.export')
    def test_process_audio_basic_operations(self, mock_export, mock_from_file, audio_processor, sample_job, temp_dir):
        """Testa processamento básico de áudio"""
        # Mock do AudioSegment
        mock_audio = Mock()
        mock_audio.set_channels.return_value = mock_audio
        mock_audio.set_frame_rate.return_value = mock_audio
        mock_from_file.return_value = mock_audio
        
        # Cria arquivo de entrada real
        input_file = temp_dir / "test_input.mp3"
        input_file.write_bytes(b'\xff\xfb\x90\x00' + b'\x00' * 1000)
        sample_job.input_file = str(input_file)
        
        # Configura job store mock
        audio_processor.job_store = Mock()
        audio_processor.job_store.update_job = Mock()
        
        # Processa áudio
        result = audio_processor.process_audio(sample_job)
        
        # Verifica resultado
        assert result.status == JobStatus.COMPLETED
        assert result.progress == 100.0
        assert result.completed_at is not None
        
        # Verifica se operações foram chamadas
        mock_from_file.assert_called_once()
        mock_export.assert_called_once()
    
    def test_process_audio_no_operations(self, audio_processor, temp_dir):
        """Testa job sem operações ativas"""
        # Cria job sem operações
        job = Job.create_new(
            input_file="/tmp/test.mp3",
            isolate_vocals=False,
            remove_noise=False,
            normalize_volume=False,
            convert_to_mono=False,
            apply_highpass_filter=False,
            set_sample_rate_16k=False
        )
        
        # Cria arquivo de entrada
        input_file = temp_dir / "test_no_ops.mp3"
        input_file.write_bytes(b'\xff\xfb\x90\x00' + b'\x00' * 100)
        job.input_file = str(input_file)
        
        # Processa
        result = audio_processor.process_audio(job)
        
        # Deve completar sem processamento
        assert result.status == JobStatus.COMPLETED
        assert result.output_file is None
        assert result.progress == 100.0
    
    def test_process_audio_file_not_found(self, audio_processor, sample_job):
        """Testa processamento com arquivo inexistente"""
        sample_job.input_file = "/nonexistent/path/file.mp3"
        
        result = audio_processor.process_audio(sample_job)
        
        assert result.status == JobStatus.FAILED
        assert "não encontrado" in result.error_message
    
    @patch('app.processor_new.AudioSegment.from_file')
    def test_process_audio_invalid_format(self, mock_from_file, audio_processor, sample_job, temp_dir):
        """Testa processamento com formato inválido"""
        # Mock que simula erro de carregamento
        mock_from_file.side_effect = Exception("Invalid audio format")
        
        # Cria arquivo de entrada
        input_file = temp_dir / "invalid.mp3"
        input_file.write_bytes(b"invalid audio content")
        sample_job.input_file = str(input_file)
        
        result = audio_processor.process_audio(sample_job)
        
        assert result.status == JobStatus.FAILED
        assert "Invalid audio format" in result.error_message
    
    def test_get_file_path_existing(self, audio_processor, temp_dir):
        """Testa obtenção de caminho de arquivo existente"""
        # Cria arquivo de saída
        output_file = temp_dir / "output.opus"
        output_file.write_bytes(b"processed audio")
        
        job = Job(
            id="test-output",
            input_file="/tmp/input.mp3",
            output_file=str(output_file),
            status=JobStatus.COMPLETED,
            isolate_vocals=False,
            remove_noise=True,
            normalize_volume=True,
            convert_to_mono=True,
            apply_highpass_filter=True,
            set_sample_rate_16k=True,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1)
        )
        
        file_path = audio_processor.get_file_path(job)
        
        assert file_path is not None
        assert file_path.exists()
        assert str(file_path) == str(output_file)
    
    def test_get_file_path_nonexistent(self, audio_processor):
        """Testa obtenção de caminho de arquivo inexistente"""
        job = Job(
            id="test-no-output",
            input_file="/tmp/input.mp3",
            output_file="/nonexistent/output.opus",
            status=JobStatus.COMPLETED,
            isolate_vocals=False,
            remove_noise=True,
            normalize_volume=True,
            convert_to_mono=True,
            apply_highpass_filter=True,
            set_sample_rate_16k=True,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1)
        )
        
        file_path = audio_processor.get_file_path(job)
        
        assert file_path is None


class TestSystemIntegration:
    """Testes de integração do sistema completo"""
    
    @pytest.fixture
    def integrated_system(self, job_store):
        """Sistema integrado para testes"""
        processor = AudioProcessor(job_store=job_store)
        return {
            'job_store': job_store,
            'processor': processor
        }
    
    async def test_complete_job_lifecycle(self, integrated_system, temp_dir):
        """Testa ciclo completo de um job"""
        job_store = integrated_system['job_store']
        processor = integrated_system['processor']
        
        # 1. Cria arquivo de entrada
        input_file = temp_dir / "lifecycle_test.mp3"
        input_file.write_bytes(b'\xff\xfb\x90\x00' + b'\x00' * 2000)
        
        # 2. Cria job
        job = Job.create_new(
            input_file=str(input_file),
            remove_noise=True,
            normalize_volume=True,
            convert_to_mono=True
        )
        
        # 3. Salva no store
        job_store.save_job(job)
        
        # 4. Verifica job foi salvo
        retrieved_job = job_store.get_job(job.id)
        assert retrieved_job is not None
        assert retrieved_job.status == JobStatus.QUEUED
        
        # 5. Simula processamento com mocks
        with patch('app.processor_new.AudioSegment.from_file') as mock_from_file, \
             patch('app.processor_new.AudioSegment.export') as mock_export, \
             patch('app.processor_new.pydub_normalize') as mock_normalize:
            
            # Mock do áudio
            mock_audio = Mock()
            mock_audio.set_channels.return_value = mock_audio
            mock_from_file.return_value = mock_audio
            mock_normalize.return_value = mock_audio
            
            # Processa
            processed_job = processor.process_audio(retrieved_job)
        
        # 6. Verifica processamento
        assert processed_job.status == JobStatus.COMPLETED
        assert processed_job.progress == 100.0
        assert processed_job.completed_at is not None
        
        # 7. Atualiza no store
        job_store.update_job(processed_job)
        
        # 8. Verifica job final
        final_job = job_store.get_job(job.id)
        assert final_job.status == JobStatus.COMPLETED
    
    def test_job_caching_behavior(self, integrated_system, temp_dir):
        """Testa comportamento de cache de jobs"""
        job_store = integrated_system['job_store']
        
        # Cria arquivo
        input_file = temp_dir / "cache_test.mp3"
        input_file.write_bytes(b'\xff\xfb\x90\x00' + b'\x00' * 1000)
        
        # Cria dois jobs idênticos
        job1 = Job.create_new(
            input_file=str(input_file),
            remove_noise=True,
            normalize_volume=True
        )
        
        job2 = Job.create_new(
            input_file=str(input_file),
            remove_noise=True,
            normalize_volume=True
        )
        
        # IDs devem ser iguais (comportamento de cache)
        assert job1.id == job2.id
        
        # Salva primeiro job
        job_store.save_job(job1)
        
        # Tenta salvar segundo job (deve sobrescrever)
        job_store.save_job(job2)
        
        # Deve haver apenas um job no store
        retrieved = job_store.get_job(job1.id)
        assert retrieved is not None
    
    async def test_error_handling_integration(self, integrated_system, temp_dir):
        """Testa tratamento de erros integrado"""
        job_store = integrated_system['job_store']
        processor = integrated_system['processor']
        
        # Job com arquivo inexistente
        job = Job.create_new(
            input_file="/absolutely/nonexistent/file.mp3",
            remove_noise=True
        )
        
        job_store.save_job(job)
        
        # Processa (deve falhar)
        processed_job = processor.process_audio(job)
        
        # Verifica falha
        assert processed_job.status == JobStatus.FAILED
        assert processed_job.error_message is not None
        
        # Atualiza no store
        job_store.update_job(processed_job)
        
        # Verifica persistência do erro
        retrieved_job = job_store.get_job(job.id)
        assert retrieved_job.status == JobStatus.FAILED
        assert retrieved_job.error_message == processed_job.error_message