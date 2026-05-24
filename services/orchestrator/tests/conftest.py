"""
Fixtures compartilhadas para testes.
"""
import asyncio
from typing import Any, AsyncGenerator, Dict, Generator, Tuple
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import pytest_asyncio

from common.test_utils.mock_redis import MockRedis
from common.test_utils.mock_celery import mock_celery_app

from domain.models import PipelineJob, PipelineStatus, PipelineStage, StageStatus
from infrastructure.circuit_breaker import CircuitBreaker, CircuitState


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Cria event loop para testes async."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def fake_redis():
    """Fake Redis instance from common test utils."""
    return MockRedis.create_fake_redis()


@pytest.fixture
def mock_redis() -> Mock:
    """Mock do Redis."""
    redis = Mock()
    redis.get.return_value = None
    redis.set.return_value = True
    redis.delete.return_value = 1
    redis.zadd.return_value = 1
    redis.zrem.return_value = 1
    redis.zrevrange.return_value = []
    redis.zcard.return_value = 0
    redis.ping.return_value = True
    return redis


@pytest.fixture
def mock_redis_store():
    """Orchestrator job store backed by fake Redis."""
    from infrastructure.redis_store import OrchestratorJobStore
    return MockRedis.create_job_store(OrchestratorJobStore)


@pytest.fixture
def mock_celery():
    """Mock Celery app."""
    return mock_celery_app()


@pytest.fixture
def mock_orchestrator():
    """Mock pipeline orchestrator."""
    orchestrator = MagicMock()
    orchestrator.start_pipeline = AsyncMock()
    orchestrator.get_pipeline_status = MagicMock()
    return orchestrator


@pytest.fixture
def circuit_breaker() -> CircuitBreaker:
    """Circuit breaker para testes."""
    return CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=60,
        half_open_max_calls=2,
        name="test-cb",
    )


@pytest.fixture
def mock_microservice_client() -> AsyncMock:
    """Mock de cliente de microserviço."""
    client = AsyncMock()
    client.submit_job.return_value = {"job_id": "test-123", "status": "queued"}
    client.submit_multipart.return_value = {"job_id": "test-456", "status": "queued"}
    client.get_job_status.return_value = {"job_id": "test-123", "status": "completed", "progress": 1.0}
    client.check_health.return_value = {"status": "healthy", "version": "1.0.0"}
    client.download_file.return_value = (b"test content", "test-file.mp3")
    client.base_url = "http://localhost:8000"
    client.timeout = 30
    client.service_name = "test-service"
    return client


@pytest.fixture
def sample_pipeline_job() -> PipelineJob:
    """Job de exemplo para testes."""
    return PipelineJob.create_new(
        youtube_url="https://www.youtube.com/watch?v=test123",
        language="pt",
    )


@pytest.fixture
def completed_pipeline_job() -> PipelineJob:
    """Job completo para testes."""
    job = PipelineJob.create_new(
        youtube_url="https://www.youtube.com/watch?v=test123",
        language="pt",
    )
    job.download_stage.complete("audio.mp3")
    job.normalization_stage.complete("normalized.mp3")
    job.transcription_stage.complete("transcription.txt")
    job.transcription_text = "Test transcription"
    job.mark_as_completed()
    return job


@pytest.fixture
def failed_pipeline_job() -> PipelineJob:
    """Job falho para testes."""
    job = PipelineJob.create_new(
        youtube_url="https://www.youtube.com/watch?v=test123",
        language="pt",
    )
    job.download_stage.fail("Connection timeout")
    job.mark_as_failed("Download failed")
    return job


@pytest_asyncio.fixture
async def async_mock_response() -> AsyncMock:
    """Mock de resposta HTTP async."""
    response = AsyncMock()
    response.status_code = 200
    response.json.return_value = {"status": "ok"}
    response.text = "OK"
    response.headers = {}
    return response


@pytest.fixture
def mock_health_checker() -> AsyncMock:
    """Mock do health checker."""
    checker = AsyncMock()
    checker.check_all.return_value = {
        "video-downloader": "healthy",
        "audio-normalization": "healthy",
        "audio-transcriber": "healthy",
    }
    return checker
