"""
Testes para VideoUploadService.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock
from fastapi import UploadFile
from io import BytesIO

from src.infrastructure.storage.video_upload_service import VideoUploadService
from src.domain.value_objects import UploadedVideoFile
from src.domain.exceptions import StorageError


class TestVideoUploadService:
    """Testes para serviço de upload."""
    
    @pytest.fixture
    def mock_storage(self, tmp_path):
        """Mock do storage service."""
        mock = Mock()
        mock.create_temp_directory = AsyncMock(return_value=tmp_path)
        return mock
    
    @pytest.fixture
    def upload_service(self, mock_storage):
        """Fixture para upload service."""
        return VideoUploadService(mock_storage)
    
    @pytest.mark.asyncio
    async def test_save_upload_success(self, upload_service, mock_storage, tmp_path):
        """Testa salvamento bem-sucedido."""
        # Arrange
        content = b"fake video content"
        upload_file = UploadFile(
            filename="test_video.mp4",
            file=BytesIO(content)
        )
        upload_file.content_type = "video/mp4"
        
        # Act
        result = await upload_service.save_upload(upload_file)
        
        # Assert
        assert isinstance(result, UploadedVideoFile)
        assert result.original_filename == "test_video.mp4"
        assert result.mime_type == "video/mp4"
        assert result.size_bytes == len(content)
        assert result.file_path.exists()
        assert result.file_path.read_bytes() == content
    
    @pytest.mark.asyncio
    async def test_save_upload_with_temp_dir(self, upload_service, tmp_path):
        """Testa salvamento com diretório temporário especificado."""
        # Arrange
        custom_temp = tmp_path / "custom"
        custom_temp.mkdir()
        
        content = b"test content"
        upload_file = UploadFile(
            filename="test.mp4",
            file=BytesIO(content)
        )
        
        # Act
        result = await upload_service.save_upload(upload_file, custom_temp)
        
        # Assert
        assert result.file_path.parent == custom_temp
        assert result.file_path.exists()
    
    def test_sanitize_filename_removes_path_separators(self, upload_service):
        """Testa remoção de separadores de caminho."""
        # Act
        result = upload_service._sanitize_filename("../../../etc/passwd")
        
        # Assert
        assert '/' not in result
        assert '..' not in result
        assert result == "______etc_passwd"
    
    def test_sanitize_filename_removes_dangerous_chars(self, upload_service):
        """Testa remoção de caracteres perigosos."""
        # Act
        result = upload_service._sanitize_filename('test<>:"|?*.mp4')
        
        # Assert
        assert '<' not in result
        assert '>' not in result
        assert ':' not in result
        assert '"' not in result
        assert '|' not in result
        assert '?' not in result
        assert result == "test_______.mp4"
    
    def test_sanitize_filename_adds_extension_if_missing(self, upload_service):
        """Testa adição de extensão quando ausente."""
        # Act
        result = upload_service._sanitize_filename("noextension")
        
        # Assert
        assert result == "noextension.unknown"
    
    def test_sanitize_filename_preserves_valid_name(self, upload_service):
        """Testa preservação de nome válido."""
        # Act
        result = upload_service._sanitize_filename("valid_file_name.mp4")
        
        # Assert
        assert result == "valid_file_name.mp4"
    
    @pytest.mark.asyncio
    async def test_save_upload_chunks(self, upload_service, tmp_path):
        """Testa salvamento em chunks."""
        # Arrange
        # Criar arquivo maior que chunk_size (8KB padrão)
        large_content = b"x" * 20000  # 20KB
        upload_file = UploadFile(
            filename="large.mp4",
            file=BytesIO(large_content)
        )
        
        # Act
        result = await upload_service.save_upload(upload_file, tmp_path)
        
        # Assert
        assert result.size_bytes == 20000
        assert result.file_path.read_bytes() == large_content
    
    @pytest.mark.asyncio
    async def test_save_upload_no_content_type(self, upload_service, tmp_path):
        """Testa salvamento sem content_type."""
        # Arrange
        upload_file = UploadFile(
            filename="test.mp4",
            file=BytesIO(b"content")
        )
        upload_file.content_type = None
        
        # Act
        result = await upload_service.save_upload(upload_file, tmp_path)
        
        # Assert
        assert result.mime_type == "application/octet-stream"
    
    @pytest.mark.asyncio
    async def test_save_upload_storage_error(self, upload_service, tmp_path):
        """Testa erro de storage."""
        # Arrange
        upload_file = UploadFile(
            filename="test.mp4",
            file=BytesIO(b"content")
        )
        
        # Simular erro ao criar arquivo
        invalid_path = tmp_path / "invalid" / "path" / "that" / "doesnt" / "exist"
        
        # Act & Assert
        with pytest.raises(StorageError, match="Failed to save"):
            await upload_service.save_upload(upload_file, invalid_path)
