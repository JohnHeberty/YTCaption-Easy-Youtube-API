"""
Unit tests for AudioProcessor.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.services.audio_processor import (
    AudioProcessor,
    AudioConfig,
    FileOperations,
    VideoExtractor,
    AudioChunker,
    AudioNormalizer,
)


@pytest.fixture
def audio_config():
    """Fixture para configuração de áudio."""
    return AudioConfig({
        'temp_dir': './temp',
        'streaming_threshold_mb': 50,
        'chunking_enabled': True,
        'chunk_duration_sec': 60,
        'chunk_overlap_sec': 1,
    })


@pytest.fixture
def mock_job_store():
    """Fixture para mock de job store."""
    return Mock()


class TestAudioConfig:
    """Testes para AudioConfig."""

    def test_default_values(self):
        """Deve ter valores padrão."""
        config = AudioConfig({})
        assert config.temp_dir == Path('./temp')
        assert config.streaming_threshold_mb == 50
        assert config.chunking_enabled is True

    def test_custom_values(self, audio_config):
        """Deve aceitar valores customizados."""
        assert audio_config.streaming_threshold_mb == 50
        assert audio_config.chunk_duration_sec == 60


class TestFileOperations:
    """Testes para FileOperations."""

    def test_ensure_dir_creates_directory(self, audio_config, tmp_path):
        """Deve criar diretório se não existir."""
        file_ops = FileOperations(audio_config)
        test_dir = tmp_path / "test_dir"
        file_ops.ensure_dir(test_dir)
        assert test_dir.exists()

    def test_get_temp_dir_creates_job_directory(self, audio_config, tmp_path):
        """Deve criar diretório temporário para job."""
        audio_config.temp_dir = tmp_path
        file_ops = FileOperations(audio_config)
        temp_dir = file_ops.get_temp_dir("job_123")
        assert temp_dir.exists()
        assert "job_123" in temp_dir.name

    @patch('os.path.getsize')
    @patch('shutil.disk_usage')
    def test_check_disk_space_sufficient(self, mock_disk, mock_size, audio_config):
        """Deve retornar True quando há espaço suficiente."""
        mock_size.return_value = 100  # 100 bytes
        mock_disk.return_value = Mock(free=1000)  # 1000 bytes free
        file_ops = FileOperations(audio_config)
        result = file_ops.check_disk_space("/tmp/test.wav")
        assert result is True

    @patch('os.path.getsize')
    @patch('shutil.disk_usage')
    def test_check_disk_space_insufficient(self, mock_disk, mock_size, audio_config):
        """Deve retornar False quando não há espaço suficiente."""
        mock_size.return_value = 1000  # 1000 bytes
        mock_disk.return_value = Mock(free=100)  # 100 bytes free
        file_ops = FileOperations(audio_config)
        result = file_ops.check_disk_space("/tmp/test.wav")
        assert result is False


class TestVideoExtractor:
    """Testes para VideoExtractor."""

    def test_is_video_detects_video_extensions(self, audio_config):
        """Deve detectar extensões de vídeo."""
        file_ops = FileOperations(audio_config)
        extractor = VideoExtractor(file_ops)

        video_files = ['test.mp4', 'movie.avi', 'clip.mov', 'file.mkv', 'video.webm']
        for filename in video_files:
            assert extractor.is_video(filename) is True

    def test_is_video_rejects_audio_extensions(self, audio_config):
        """Deve rejeitar extensões de áudio."""
        file_ops = FileOperations(audio_config)
        extractor = VideoExtractor(file_ops)

        audio_files = ['song.mp3', 'recording.wav', 'audio.ogg']
        for filename in audio_files:
            assert extractor.is_video(filename) is False


class TestAudioChunker:
    """Testes para AudioChunker."""

    @patch('app.services.audio_processor.logger')
    def test_split_audio(self, mock_logger, audio_config):
        """Deve dividir áudio em chunks."""
        chunker = AudioChunker(audio_config)

        # Mock AudioSegment de 120 segundos
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=120000)  # 120000ms = 120s

        chunks = chunker.split(mock_audio)
        assert len(chunks) == 2  # 2 chunks de 60s

    def test_merge_single_chunk(self, audio_config):
        """Deve retornar chunk único sem modificação."""
        chunker = AudioChunker(audio_config)
        mock_chunk = Mock()

        result = chunker.merge([mock_chunk])
        assert result == mock_chunk

    def test_merge_multiple_chunks(self, audio_config):
        """Deve mesclar múltiplos chunks."""
        chunker = AudioChunker(audio_config)

        mock_chunk1 = Mock()
        mock_chunk2 = Mock()
        mock_chunk1.__add__ = Mock(return_value=mock_chunk2)

        result = chunker.merge([mock_chunk1, mock_chunk2])
        assert result is not None


class TestAudioNormalizer:
    """Testes para AudioNormalizer."""

    def test_convert_to_mono(self, audio_config):
        """Deve converter áudio para mono."""
        normalizer = AudioNormalizer(audio_config)

        mock_audio = Mock()
        mock_audio.set_channels.return_value = mock_audio

        result = normalizer.convert_to_mono(mock_audio)
        mock_audio.set_channels.assert_called_once_with(1)
        assert result == mock_audio

    def test_set_sample_rate(self, audio_config):
        """Deve definir sample rate."""
        normalizer = AudioNormalizer(audio_config)

        mock_audio = Mock()
        mock_audio.set_frame_rate.return_value = mock_audio

        result = normalizer.set_sample_rate(mock_audio, 16000)
        mock_audio.set_frame_rate.assert_called_once_with(16000)
        assert result == mock_audio


class TestAudioProcessor:
    """Testes para AudioProcessor principal."""

    def test_set_job_store(self, audio_config, mock_job_store):
        """Deve injetar job store."""
        processor = AudioProcessor(audio_config)
        processor.set_job_store(mock_job_store)
        assert processor.job_store == mock_job_store

    def test_update_job_calls_store(self, audio_config, mock_job_store):
        """Deve chamar job store ao atualizar."""
        processor = AudioProcessor(audio_config)
        processor.set_job_store(mock_job_store)

        mock_job = Mock()
        processor._update_job(mock_job)

        mock_job_store.update_job.assert_called_once_with(mock_job)
