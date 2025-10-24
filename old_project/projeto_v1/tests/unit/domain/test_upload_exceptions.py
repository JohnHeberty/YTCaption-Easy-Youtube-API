"""
Testes para exceções de upload de vídeo.
"""
import pytest

from src.domain.exceptions import (
    VideoUploadError,
    UnsupportedFormatError,
    FileTooLargeError,
    InvalidVideoFileError
)


class TestVideoUploadExceptions:
    """Testes para exceções de upload."""
    
    def test_video_upload_error_base(self):
        """Testa exceção base VideoUploadError."""
        # Act
        error = VideoUploadError("Upload failed")
        
        # Assert
        assert str(error) == "Upload failed"
        assert isinstance(error, Exception)
    
    def test_unsupported_format_error(self):
        """Testa UnsupportedFormatError."""
        # Arrange
        supported = ['.mp4', '.avi', '.mov']
        
        # Act
        error = UnsupportedFormatError('.xyz', supported)
        
        # Assert
        assert '.xyz' in str(error)
        assert 'not supported' in str(error)
        assert error.format == '.xyz'
        assert error.supported_formats == supported
    
    def test_file_too_large_error(self):
        """Testa FileTooLargeError."""
        # Act
        error = FileTooLargeError(3000.5, 2500)
        
        # Assert
        assert '3000.50MB' in str(error)
        assert '2500MB' in str(error)
        assert error.size_mb == 3000.5
        assert error.max_size_mb == 2500
    
    def test_invalid_video_file_error(self):
        """Testa InvalidVideoFileError."""
        # Act
        error = InvalidVideoFileError("File is corrupted")
        
        # Assert
        assert "File is corrupted" in str(error)
        assert error.reason == "File is corrupted"
    
    def test_exception_inheritance(self):
        """Testa hierarquia de exceções."""
        # Act
        unsupported = UnsupportedFormatError('.xyz', ['.mp4'])
        file_large = FileTooLargeError(3000, 2500)
        invalid = InvalidVideoFileError("Corrupted")
        
        # Assert
        assert isinstance(unsupported, VideoUploadError)
        assert isinstance(file_large, VideoUploadError)
        assert isinstance(invalid, VideoUploadError)
    
    def test_can_catch_with_base_exception(self):
        """Testa captura com exceção base."""
        # Act & Assert
        with pytest.raises(VideoUploadError):
            raise UnsupportedFormatError('.xyz', ['.mp4'])
        
        with pytest.raises(VideoUploadError):
            raise FileTooLargeError(3000, 2500)
        
        with pytest.raises(VideoUploadError):
            raise InvalidVideoFileError("Error")
