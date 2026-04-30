"""
Unit tests for JobService.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from datetime import timedelta

try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import datetime, timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

from app.services.job_service import (
    JobCreationService,
    JobSubmissionService,
    JobRetrievalService,
)
from app.core.models import Job, JobStatus
from app.core.exceptions import JobNotFoundError, RedisError


@pytest.fixture
def mock_job_store():
    """Fixture para mock de job store."""
    return Mock()


@pytest.fixture
def temp_upload_dir(tmp_path):
    """Fixture para diretório de upload temporário."""
    return tmp_path / "uploads"


class TestJobCreationService:
    """Testes para JobCreationService."""

    def test_create_job_entity(self, mock_job_store, temp_upload_dir):
        """Deve criar entidade Job corretamente."""
        service = JobCreationService(
            mock_job_store,
            temp_upload_dir,
            max_file_size_mb=100
        )

        job = service.create_job_entity(
            filename="test.mp3",
            processing_params={
                'remove_noise': True,
                'convert_to_mono': False,
            }
        )

        assert isinstance(job, Job)
        assert job.filename == "test.mp3"
        assert job.remove_noise is True
        assert job.convert_to_mono is False
        assert job.status == JobStatus.QUEUED

    def test_save_file_creates_directory(self, mock_job_store, temp_upload_dir):
        """Deve criar diretório se não existir."""
        service = JobCreationService(
            mock_job_store,
            temp_upload_dir,
            max_file_size_mb=100
        )

        job = Mock()
        job.id = "test_job_123"

        file_path = service.save_file(job, b"test content", ".mp3")

        assert temp_upload_dir.exists()
        assert file_path.exists()
        assert file_path.name == "test_job_123.mp3"


class TestJobSubmissionService:
    """Testes para JobSubmissionService."""

    def test_check_existing_job_returns_none_if_not_exists(self, mock_job_store):
        """Deve retornar None se job não existe."""
        mock_job_store.get_job.return_value = None
        service = JobSubmissionService(mock_job_store)

        new_job = Mock()
        new_job.id = "new_job"

        result = service.check_existing_job(new_job)
        assert result is None

    def test_check_existing_job_returns_completed_job(self, mock_job_store):
        """Deve retornar job completado do cache."""
        existing_job = Mock()
        existing_job.status = JobStatus.COMPLETED
        existing_job.created_at = now_brazil()

        mock_job_store.get_job.return_value = existing_job
        service = JobSubmissionService(mock_job_store)

        new_job = Mock()
        new_job.id = "existing_job"

        result = service.check_existing_job(new_job)
        assert result == existing_job

    def test_check_existing_job_detects_orphan(self, mock_job_store):
        """Deve detectar job órfão."""
        old_job = Mock()
        old_job.status = JobStatus.PROCESSING
        # Job criado há mais de 30 minutos
        old_job.created_at = now_brazil() - timedelta(minutes=60)

        mock_job_store.get_job.return_value = old_job
        service = JobSubmissionService(mock_job_store)

        new_job = Mock()
        new_job.id = "orphan_job"

        result = service.check_existing_job(new_job)
        assert result.status == JobStatus.QUEUED
        mock_job_store.update_job.assert_called_once()

    def test_check_existing_job_restarts_failed_job(self, mock_job_store):
        """Deve reiniciar job falhado."""
        failed_job = Mock()
        failed_job.status = JobStatus.FAILED
        failed_job.created_at = now_brazil()

        mock_job_store.get_job.return_value = failed_job
        service = JobSubmissionService(mock_job_store)

        new_job = Mock()
        new_job.id = "failed_job"

        result = service.check_existing_job(new_job)
        assert result.status == JobStatus.QUEUED
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_submit_for_processing_success(self, mock_job_store):
        """Deve submeter job para processamento."""
        service = JobSubmissionService(mock_job_store)

        mock_job = Mock()
        mock_job.id = "test_job"
        mock_job.model_dump.return_value = {"id": "test_job"}

        with patch('app.services.job_service.normalize_audio_task') as mock_task:
            mock_task.apply_async.return_value = Mock(id="celery_task_id")
            await service.submit_for_processing(mock_job)
            mock_task.apply_async.assert_called_once()


class TestJobRetrievalService:
    """Testes para JobRetrievalService."""

    def test_get_job_success(self, mock_job_store):
        """Deve retornar job existente."""
        mock_job = Mock()
        mock_job_store.get_job.return_value = mock_job

        service = JobRetrievalService(mock_job_store)
        result = service.get_job("existing_job")

        assert result == mock_job
        mock_job_store.get_job.assert_called_once_with("existing_job")

    def test_get_job_not_found_raises_error(self, mock_job_store):
        """Deve lançar erro se job não encontrado."""
        mock_job_store.get_job.return_value = None

        service = JobRetrievalService(mock_job_store)
        with pytest.raises(JobNotFoundError) as exc:
            service.get_job("missing_job")
        assert "missing_job" in str(exc.value)

    def test_get_job_redis_error_raises_redis_error(self, mock_job_store):
        """Deve lançar RedisError em erro de conexão."""
        mock_job_store.get_job.side_effect = Exception("Connection refused")

        service = JobRetrievalService(mock_job_store)
        with pytest.raises(RedisError):
            service.get_job("any_job")

    def test_get_job_with_expiration_check_expired(self, mock_job_store):
        """Deve lançar erro se job expirado."""
        mock_job = Mock()
        mock_job.is_expired = True
        mock_job_store.get_job.return_value = mock_job

        service = JobRetrievalService(mock_job_store)
        from app.core.exceptions import JobExpiredError
        with pytest.raises(JobExpiredError):
            service.get_job_with_expiration_check("expired_job")

    def test_list_recent_jobs_success(self, mock_job_store):
        """Deve listar jobs recentes."""
        mock_jobs = [Mock(), Mock()]
        mock_job_store.list_jobs.return_value = mock_jobs

        service = JobRetrievalService(mock_job_store)
        result = service.list_recent_jobs(limit=10)

        assert result == mock_jobs
        mock_job_store.list_jobs.assert_called_once_with(10)

    def test_list_recent_jobs_error_raises_redis_error(self, mock_job_store):
        """Deve lançar RedisError em erro."""
        mock_job_store.list_jobs.side_effect = Exception("Connection lost")

        service = JobRetrievalService(mock_job_store)
        with pytest.raises(RedisError):
            service.list_recent_jobs()
