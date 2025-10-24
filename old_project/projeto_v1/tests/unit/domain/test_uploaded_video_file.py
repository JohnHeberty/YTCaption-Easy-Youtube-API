"""
Testes para UploadedVideoFile value object.
"""
import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.domain.value_objects import UploadedVideoFile


class TestUploadedVideoFile:
    """Testes para UploadedVideoFile."""
    
    def test_create_uploaded_video_file_success(self, tmp_path):
        """Testa criação bem-sucedida de UploadedVideoFile."""
        # Arrange
        test_file = tmp_path / "test_video.mp4"
        test_file.write_bytes(b"fake video content")
        
        # Act
        video_file = UploadedVideoFile(
            file_path=test_file,
            original_filename="test_video.mp4",
            mime_type="video/mp4",
            size_bytes=1000000
        )
        
        # Assert
        assert video_file.file_path == test_file
        assert video_file.original_filename == "test_video.mp4"
        assert video_file.mime_type == "video/mp4"
        assert video_file.size_bytes == 1000000
        assert video_file.duration_seconds is None
    
    def test_create_with_duration(self, tmp_path):
        """Testa criação com duração especificada."""
        # Arrange
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"content")
        
        # Act
        video_file = UploadedVideoFile(
            file_path=test_file,
            original_filename="test.mp4",
            mime_type="video/mp4",
            size_bytes=1000,
            duration_seconds=120.5
        )
        
        # Assert
        assert video_file.duration_seconds == 120.5
    
    def test_file_not_found_raises_error(self, tmp_path):
        """Testa erro quando arquivo não existe."""
        # Arrange
        non_existent = tmp_path / "non_existent.mp4"
        
        # Act & Assert
        with pytest.raises(ValueError, match="File not found"):
            UploadedVideoFile(
                file_path=non_existent,
                original_filename="test.mp4",
                mime_type="video/mp4",
                size_bytes=1000
            )
    
    def test_zero_size_raises_error(self, tmp_path):
        """Testa erro com tamanho zero."""
        # Arrange
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"content")
        
        # Act & Assert
        with pytest.raises(ValueError, match="File size must be positive"):
            UploadedVideoFile(
                file_path=test_file,
                original_filename="test.mp4",
                mime_type="video/mp4",
                size_bytes=0
            )
    
    def test_negative_size_raises_error(self, tmp_path):
        """Testa erro com tamanho negativo."""
        # Arrange
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"content")
        
        # Act & Assert
        with pytest.raises(ValueError, match="File size must be positive"):
            UploadedVideoFile(
                file_path=test_file,
                original_filename="test.mp4",
                mime_type="video/mp4",
                size_bytes=-100
            )
    
    def test_empty_filename_raises_error(self, tmp_path):
        """Testa erro com nome de arquivo vazio."""
        # Arrange
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"content")
        
        # Act & Assert
        with pytest.raises(ValueError, match="Original filename is required"):
            UploadedVideoFile(
                file_path=test_file,
                original_filename="",
                mime_type="video/mp4",
                size_bytes=1000
            )
    
    def test_get_extension(self, tmp_path):
        """Testa obtenção de extensão do arquivo."""
        # Arrange
        test_file = tmp_path / "test_video.MP4"
        test_file.write_bytes(b"content")
        
        video_file = UploadedVideoFile(
            file_path=test_file,
            original_filename="test_video.MP4",
            mime_type="video/mp4",
            size_bytes=1000
        )
        
        # Act
        extension = video_file.get_extension()
        
        # Assert
        assert extension == ".mp4"  # lowercase
    
    def test_is_video_returns_true(self, tmp_path):
        """Testa identificação de arquivo de vídeo."""
        # Arrange
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"content")
        
        video_file = UploadedVideoFile(
            file_path=test_file,
            original_filename="test.mp4",
            mime_type="video/mp4",
            size_bytes=1000
        )
        
        # Act & Assert
        assert video_file.is_video() is True
        assert video_file.is_audio() is False
    
    def test_is_audio_returns_true(self, tmp_path):
        """Testa identificação de arquivo de áudio."""
        # Arrange
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"content")
        
        audio_file = UploadedVideoFile(
            file_path=test_file,
            original_filename="test.mp3",
            mime_type="audio/mpeg",
            size_bytes=1000
        )
        
        # Act & Assert
        assert audio_file.is_audio() is True
        assert audio_file.is_video() is False
    
    def test_get_size_mb(self, tmp_path):
        """Testa cálculo de tamanho em MB."""
        # Arrange
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"content")
        
        video_file = UploadedVideoFile(
            file_path=test_file,
            original_filename="test.mp4",
            mime_type="video/mp4",
            size_bytes=5_242_880  # 5MB
        )
        
        # Act
        size_mb = video_file.get_size_mb()
        
        # Assert
        assert size_mb == 5.0
    
    def test_immutability(self, tmp_path):
        """Testa que UploadedVideoFile é imutável."""
        # Arrange
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"content")
        
        video_file = UploadedVideoFile(
            file_path=test_file,
            original_filename="test.mp4",
            mime_type="video/mp4",
            size_bytes=1000
        )
        
        # Act & Assert
        with pytest.raises(Exception):  # FrozenInstanceError
            video_file.size_bytes = 2000
    
    def test_different_mime_types(self, tmp_path):
        """Testa diferentes tipos MIME."""
        # Arrange
        test_file = tmp_path / "test.avi"
        test_file.write_bytes(b"content")
        
        # Act
        video_file = UploadedVideoFile(
            file_path=test_file,
            original_filename="test.avi",
            mime_type="video/x-msvideo",
            size_bytes=1000
        )
        
        # Assert
        assert video_file.is_video() is True
        assert video_file.get_extension() == ".avi"
    
    def test_equality(self, tmp_path):
        """Testa igualdade entre UploadedVideoFile."""
        # Arrange
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"content")
        
        video1 = UploadedVideoFile(
            file_path=test_file,
            original_filename="test.mp4",
            mime_type="video/mp4",
            size_bytes=1000
        )
        
        video2 = UploadedVideoFile(
            file_path=test_file,
            original_filename="test.mp4",
            mime_type="video/mp4",
            size_bytes=1000
        )
        
        # Act & Assert
        assert video1 == video2
    
    def test_hash(self, tmp_path):
        """Testa que UploadedVideoFile é hashable."""
        # Arrange
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"content")
        
        video_file = UploadedVideoFile(
            file_path=test_file,
            original_filename="test.mp4",
            mime_type="video/mp4",
            size_bytes=1000
        )
        
        # Act & Assert
        # Deve ser possível adicionar a um set
        file_set = {video_file}
        assert len(file_set) == 1
