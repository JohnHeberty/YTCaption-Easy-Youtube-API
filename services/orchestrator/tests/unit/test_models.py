"""
Testes unitários para Models.
"""
import pytest

from domain.models import (
    PipelineJob,
    PipelineStatus,
    PipelineStage,
    StageStatus,
    TranscriptionSegment,
)


class TestTranscriptionSegment:
    """Testes para TranscriptionSegment."""

    def test_creation(self):
        """Deve criar segmento."""
        segment = TranscriptionSegment(
            text="Hello world",
            start=0.0,
            end=2.5,
            duration=2.5,
        )
        assert segment.text == "Hello world"
        assert segment.duration == 2.5


class TestPipelineStage:
    """Testes para PipelineStage."""

    def test_creation(self):
        """Deve criar estágio."""
        stage = PipelineStage(name="download")
        assert stage.name == "download"
        assert stage.status == StageStatus.PENDING
        assert stage.progress == 0.0

    def test_start(self):
        """Deve iniciar estágio."""
        stage = PipelineStage(name="download")
        stage.start()
        assert stage.status == StageStatus.PROCESSING
        assert stage.started_at is not None

    def test_complete(self):
        """Deve completar estágio."""
        stage = PipelineStage(name="download")
        stage.complete("output.mp3")
        assert stage.status == StageStatus.COMPLETED
        assert stage.progress == 100.0
        assert stage.output_file == "output.mp3"
        assert stage.completed_at is not None

    def test_fail(self):
        """Deve marcar estágio como falho."""
        stage = PipelineStage(name="download")
        stage.fail("Connection timeout")
        assert stage.status == StageStatus.FAILED
        assert stage.error_message == "Connection timeout"
        assert stage.completed_at is not None


class TestPipelineJob:
    """Testes para PipelineJob."""

    def test_create_new(self):
        """Deve criar novo job."""
        job = PipelineJob.create_new("https://youtube.com/watch?v=test")
        assert job.id is not None
        assert len(job.id) == 16  # SHA256[:16]
        assert job.youtube_url == "https://youtube.com/watch?v=test"
        assert job.status == PipelineStatus.QUEUED

    def test_update_progress(self):
        """Deve atualizar progresso."""
        job = PipelineJob.create_new("https://youtube.com/watch?v=test")
        job.download_stage.complete("audio.mp3")
        job.update_progress()
        assert abs(job.overall_progress - 33.33333333333333) < 0.001

    def test_get_current_stage(self):
        """Deve retornar estágio atual."""
        job = PipelineJob.create_new("https://youtube.com/watch?v=test")
        job.download_stage.start()
        current = job.get_current_stage()
        assert current.name == "download"

    def test_mark_as_completed(self):
        """Deve marcar como completo."""
        job = PipelineJob.create_new("https://youtube.com/watch?v=test")
        job.mark_as_completed()
        assert job.status == PipelineStatus.COMPLETED
        assert job.overall_progress == 100.0

    def test_mark_as_failed(self):
        """Deve marcar como falho."""
        job = PipelineJob.create_new("https://youtube.com/watch?v=test")
        job.mark_as_failed("Something went wrong")
        assert job.status == PipelineStatus.FAILED
        assert job.error_message == "Something went wrong"

    def test_stages_created(self):
        """Deve criar estágios automaticamente."""
        job = PipelineJob.create_new("https://youtube.com/watch?v=test")
        assert job.download_stage.name == "download"
        assert job.normalization_stage.name == "normalization"
        assert job.transcription_stage.name == "transcription"

    def test_configuration_params(self):
        """Deve aceitar parâmetros de configuração."""
        job = PipelineJob.create_new(
            "https://youtube.com/watch?v=test",
            language="en",
            remove_noise=False,
            convert_to_mono=False,
        )
        assert job.language == "en"
        assert job.remove_noise is False
        assert job.convert_to_mono is False
