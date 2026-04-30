"""
Testes unitários para PipelineOrchestrator.
"""
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from domain.models import PipelineJob, PipelineStatus
from services.pipeline_orchestrator import PipelineOrchestrator


class TestPipelineOrchestrator:
    """Testes para PipelineOrchestrator."""

    @pytest.fixture
    def orchestrator(self, mock_microservice_client, mock_health_checker):
        """Cria orquestrador com mocks."""
        return PipelineOrchestrator(
            video_client=mock_microservice_client,
            audio_client=mock_microservice_client,
            transcription_client=mock_microservice_client,
            health_checker=mock_health_checker,
            redis_store=None,
        )

    @pytest.mark.asyncio
    async def test_execute_pipeline_success(
        self, orchestrator, sample_pipeline_job
    ):
        """Deve executar pipeline com sucesso."""
        # Configura mocks para sucesso em todos os estágios
        orchestrator._video_client.submit_job.return_value = {"job_id": "dl-123"}
        orchestrator._video_client.get_job_status.return_value = {
            "job_id": "dl-123",
            "status": "completed",
            "progress": 1.0,
        }
        orchestrator._video_client.download_file.return_value = (b"audio data", "audio.mp3")

        orchestrator._audio_client.submit_multipart.return_value = {"job_id": "norm-123"}
        orchestrator._audio_client.get_job_status.return_value = {
            "job_id": "norm-123",
            "status": "completed",
            "progress": 1.0,
        }
        orchestrator._audio_client.download_file.return_value = (b"normalized audio", "normalized.mp3")

        orchestrator._transcription_client.submit_multipart.return_value = {"job_id": "trans-123"}
        orchestrator._transcription_client.get_job_status.return_value = {
            "job_id": "trans-123",
            "status": "completed",
            "progress": 1.0,
        }
        orchestrator._transcription_client.download_file.return_value = (b"transcription data", "transcription.txt")

        result = await orchestrator.execute_pipeline(sample_pipeline_job)

        assert result.status == PipelineStatus.COMPLETED
        assert result.overall_progress == 100.0

    @pytest.mark.asyncio
    async def test_execute_pipeline_download_fails(
        self, orchestrator, sample_pipeline_job
    ):
        """Deve falhar quando download falha."""
        orchestrator._video_client.submit_job.side_effect = Exception("Connection error")

        result = await orchestrator.execute_pipeline(sample_pipeline_job)

        assert result.status == PipelineStatus.FAILED
        assert "Download failed" in result.error_message

    @pytest.mark.asyncio
    async def test_check_services_health(self, orchestrator):
        """Deve verificar saúde dos serviços."""
        orchestrator._health_checker.check_all.return_value = {
            "video-downloader": "healthy",
            "audio-normalization": "healthy",
            "audio-transcriber": "healthy",
        }

        result = await orchestrator.check_services_health()

        assert result["video-downloader"] == "healthy"
        assert result["audio-normalization"] == "healthy"
        assert result["audio-transcriber"] == "healthy"

    @pytest.mark.asyncio
    async def test_execute_pipeline_handles_exceptions(
        self, orchestrator, sample_pipeline_job
    ):
        """Deve lidar com exceções não esperadas."""
        orchestrator._video_client.submit_job.side_effect = RuntimeError("Unexpected error")

        result = await orchestrator.execute_pipeline(sample_pipeline_job)

        assert result.status == PipelineStatus.FAILED

    @pytest.mark.asyncio
    async def test_pipeline_with_redis(self, mock_microservice_client, mock_health_checker, sample_pipeline_job):
        """Deve salvar no Redis se disponível."""
        mock_redis = Mock()
        mock_redis.save_job.return_value = True

        orchestrator = PipelineOrchestrator(
            video_client=mock_microservice_client,
            audio_client=mock_microservice_client,
            transcription_client=mock_microservice_client,
            health_checker=mock_health_checker,
            redis_store=mock_redis,
        )

        # Configura mocks
        mock_microservice_client.submit_job.return_value = {"job_id": "dl-123"}
        mock_microservice_client.get_job_status.return_value = {
            "status": "completed",
            "progress": 1.0,
        }
        mock_microservice_client.download_file.return_value = (b"test", "file.mp3")

        await orchestrator.execute_pipeline(sample_pipeline_job)

        # Verifica se salvou no Redis
        assert mock_redis.save_job.called
