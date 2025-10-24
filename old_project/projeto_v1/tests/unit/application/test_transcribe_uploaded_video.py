"""
Testes para TranscribeUploadedVideoUseCase.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import time

from src.application.use_cases.transcribe_uploaded_video import TranscribeUploadedVideoUseCase
from src.domain.value_objects import UploadedVideoFile
from src.domain.exceptions import (
    VideoUploadError,
    UnsupportedFormatError,
    FileTooLargeError,
    TranscriptionError,
    StorageError
)


class TestTranscribeUploadedVideoUseCase:
    """Testes para caso de uso de transcrição de upload."""
    
    @pytest.fixture
    def mock_transcription_service(self):
        """Mock do serviço de transcrição."""
        mock = Mock()
        mock.transcribe = AsyncMock(return_value={
            'text': 'Hello world',
            'segments': [
                {'text': 'Hello world', 'start': 0.0, 'end': 2.0}
            ],
            'language': 'en'
        })
        return mock
    
    @pytest.fixture
    def mock_storage_service(self):
        """Mock do serviço de storage."""
        mock = Mock()
        return mock
    
    @pytest.fixture
    def mock_upload_validator(self):
        """Mock do validador de upload."""
        mock = Mock()
        mock.validate_file = AsyncMock(return_value={
            'duration': 120.5,
            'has_video': True,
            'has_audio': True,
            'video_codec': 'h264',
            'audio_codec': 'aac'
        })
        return mock
    
    @pytest.fixture
    def use_case(self, mock_transcription_service, mock_storage_service, mock_upload_validator):
        """Fixture para use case."""
        return TranscribeUploadedVideoUseCase(
            transcription_service=mock_transcription_service,
            storage_service=mock_storage_service,
            upload_validator=mock_upload_validator
        )
    
    @pytest.fixture
    def uploaded_audio_file(self, tmp_path):
        """Arquivo de áudio fake."""
        file_path = tmp_path / "test_audio.mp3"
        file_path.write_bytes(b"fake audio content")
        
        return UploadedVideoFile(
            file_path=file_path,
            original_filename="test_audio.mp3",
            mime_type="audio/mpeg",
            size_bytes=18
        )
    
    @pytest.fixture
    def uploaded_video_file(self, tmp_path):
        """Arquivo de vídeo fake."""
        file_path = tmp_path / "test_video.mp4"
        file_path.write_bytes(b"fake video content")
        
        return UploadedVideoFile(
            file_path=file_path,
            original_filename="test_video.mp4",
            mime_type="video/mp4",
            size_bytes=18
        )
    
    @pytest.mark.asyncio
    async def test_execute_audio_file_success(self, use_case, uploaded_audio_file):
        """Testa transcrição bem-sucedida de arquivo de áudio."""
        # Act
        result = await use_case.execute(
            uploaded_file=uploaded_audio_file,
            model_size="base",
            language="en"
        )
        
        # Assert
        assert 'transcription' in result
        assert 'metadata' in result
        assert result['metadata']['original_filename'] == "test_audio.mp3"
        assert result['metadata']['format'] == "mp3"
        assert result['metadata']['type'] == "audio"
        assert result['metadata']['model_size'] == "base"
        assert result['metadata']['language'] == "en"
        assert result['metadata']['duration_seconds'] == 120.5
        assert result['metadata']['has_video'] is True
        assert result['metadata']['has_audio'] is True
    
    @pytest.mark.asyncio
    async def test_execute_video_file_with_audio_extraction(
        self,
        use_case,
        uploaded_video_file,
        tmp_path
    ):
        """Testa transcrição de vídeo com extração de áudio."""
        # Arrange
        audio_file = tmp_path / "test_video_audio.wav"
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0, stderr='')
            
            # Simular criação do arquivo de áudio
            def create_audio(*args, **kwargs):
                audio_file.write_bytes(b"extracted audio")
                return Mock(returncode=0, stderr='')
            
            mock_subprocess.side_effect = create_audio
            
            # Act
            result = await use_case.execute(
                uploaded_file=uploaded_video_file,
                model_size="small"
            )
            
            # Assert
            assert 'transcription' in result
            assert result['metadata']['type'] == "video"
            assert result['metadata']['format'] == "mp4"
            mock_subprocess.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_validation_error(
        self,
        use_case,
        uploaded_audio_file,
        mock_upload_validator
    ):
        """Testa erro de validação."""
        # Arrange
        mock_upload_validator.validate_file = AsyncMock(
            side_effect=UnsupportedFormatError("xyz", ["mp3", "mp4"])
        )
        
        # Act & Assert
        with pytest.raises(UnsupportedFormatError):
            await use_case.execute(uploaded_file=uploaded_audio_file)
    
    @pytest.mark.asyncio
    async def test_execute_file_too_large_error(
        self,
        use_case,
        uploaded_audio_file,
        mock_upload_validator
    ):
        """Testa erro de arquivo muito grande."""
        # Arrange
        mock_upload_validator.validate_file = AsyncMock(
            side_effect=FileTooLargeError(3000, 2500)
        )
        
        # Act & Assert
        with pytest.raises(FileTooLargeError):
            await use_case.execute(uploaded_file=uploaded_audio_file)
    
    @pytest.mark.asyncio
    async def test_execute_transcription_error(
        self,
        use_case,
        uploaded_audio_file,
        mock_transcription_service
    ):
        """Testa erro na transcrição."""
        # Arrange
        mock_transcription_service.transcribe = AsyncMock(
            side_effect=TranscriptionError("Transcription failed")
        )
        
        # Act & Assert
        with pytest.raises(TranscriptionError):
            await use_case.execute(uploaded_file=uploaded_audio_file)
    
    @pytest.mark.asyncio
    async def test_execute_auto_language_detection(self, use_case, uploaded_audio_file):
        """Testa detecção automática de idioma."""
        # Act
        result = await use_case.execute(
            uploaded_file=uploaded_audio_file,
            language=None  # Auto-detect
        )
        
        # Assert
        assert result['metadata']['language'] == "auto-detect"
    
    @pytest.mark.asyncio
    async def test_execute_cleanup_on_success(self, use_case, uploaded_audio_file):
        """Testa limpeza de arquivos após sucesso."""
        # Arrange
        file_path = uploaded_audio_file.file_path
        assert file_path.exists()
        
        # Act
        await use_case.execute(uploaded_file=uploaded_audio_file)
        
        # Assert - arquivo deve ser removido
        assert not file_path.exists()
    
    @pytest.mark.asyncio
    async def test_execute_cleanup_on_error(
        self,
        use_case,
        uploaded_audio_file,
        mock_transcription_service
    ):
        """Testa limpeza de arquivos após erro."""
        # Arrange
        file_path = uploaded_audio_file.file_path
        mock_transcription_service.transcribe = AsyncMock(
            side_effect=TranscriptionError("Error")
        )
        
        # Act & Assert
        with pytest.raises(TranscriptionError):
            await use_case.execute(uploaded_file=uploaded_audio_file)
        
        # Arquivo deve ser removido mesmo com erro
        assert not file_path.exists()
    
    @pytest.mark.asyncio
    async def test_execute_processing_time(self, use_case, uploaded_audio_file):
        """Testa cálculo do tempo de processamento."""
        # Act
        start = time.time()
        result = await use_case.execute(uploaded_file=uploaded_audio_file)
        duration = time.time() - start
        
        # Assert
        assert 'processing_time_seconds' in result['metadata']
        assert result['metadata']['processing_time_seconds'] > 0
        assert result['metadata']['processing_time_seconds'] <= duration + 0.1
    
    @pytest.mark.asyncio
    async def test_extract_audio_ffmpeg_error(self, use_case, tmp_path):
        """Testa erro do FFmpeg ao extrair áudio."""
        # Arrange
        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake")
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(
                returncode=1,
                stderr="FFmpeg error: invalid codec"
            )
            
            # Act & Assert
            with pytest.raises(StorageError, match="FFmpeg error"):
                await use_case._extract_audio(video_path)
    
    @pytest.mark.asyncio
    async def test_extract_audio_timeout(self, use_case, tmp_path):
        """Testa timeout na extração de áudio."""
        # Arrange
        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake")
        
        with patch('subprocess.run') as mock_subprocess:
            import subprocess
            mock_subprocess.side_effect = subprocess.TimeoutExpired(
                cmd=['ffmpeg'],
                timeout=300
            )
            
            # Act & Assert
            with pytest.raises(StorageError, match="timeout"):
                await use_case._extract_audio(video_path)
    
    @pytest.mark.asyncio
    async def test_cleanup_removes_audio_file(self, use_case, tmp_path):
        """Testa remoção de arquivo de áudio extraído."""
        # Arrange
        video_path = tmp_path / "video.mp4"
        audio_path = tmp_path / "video_audio.wav"
        
        video_path.write_bytes(b"video")
        audio_path.write_bytes(b"audio")
        
        # Act
        await use_case._cleanup_files(video_path)
        
        # Assert
        assert not video_path.exists()
        assert not audio_path.exists()
