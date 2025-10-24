"""
Testes para VideoUploadValidator.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import subprocess

from src.infrastructure.validators.video_upload_validator import VideoUploadValidator
from src.domain.exceptions import (
    UnsupportedFormatError,
    FileTooLargeError,
    InvalidVideoFileError,
    ValidationError
)


class TestVideoUploadValidator:
    """Testes para validador de upload."""
    
    @pytest.fixture
    def validator(self):
        """Fixture para validator."""
        with patch.object(VideoUploadValidator, '_check_ffprobe_available'):
            return VideoUploadValidator()
    
    def test_get_supported_formats(self, validator):
        """Testa obtenção de formatos suportados."""
        # Act
        formats = validator.get_supported_formats()
        
        # Assert
        assert '.mp4' in formats
        assert '.avi' in formats
        assert '.mp3' in formats
        assert '.wav' in formats
        assert len(formats) > 15
    
    @pytest.mark.asyncio
    async def test_validate_unsupported_format(self, validator, tmp_path):
        """Testa erro com formato não suportado."""
        # Arrange
        test_file = tmp_path / "test.xyz"
        test_file.write_bytes(b"content")
        
        # Act & Assert
        with pytest.raises(UnsupportedFormatError) as exc_info:
            await validator.validate_file(test_file, 2500, 10800)
        
        assert '.xyz' in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_validate_file_too_large(self, validator, tmp_path):
        """Testa erro com arquivo muito grande."""
        # Arrange
        test_file = tmp_path / "test.mp4"
        # Criar arquivo de 3GB (3 * 1024 * 1024 * 1024 bytes)
        test_file.write_bytes(b"x" * (3 * 1024 * 1024 * 1024))
        
        # Act & Assert
        with pytest.raises(FileTooLargeError) as exc_info:
            await validator.validate_file(test_file, 2500, 10800)
        
        assert exc_info.value.max_size_mb == 2500
    
    @pytest.mark.asyncio
    async def test_validate_success(self, validator, tmp_path):
        """Testa validação bem-sucedida."""
        # Arrange
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"x" * 1000)
        
        # Mock FFprobe response
        ffprobe_output = {
            'format': {
                'duration': '120.5',
                'size': '1000',
                'bit_rate': '128000',
                'format_name': 'mp4'
            },
            'streams': [
                {
                    'codec_type': 'video',
                    'codec_name': 'h264',
                    'width': 1920,
                    'height': 1080
                },
                {
                    'codec_type': 'audio',
                    'codec_name': 'aac',
                    'sample_rate': '48000',
                    'channels': 2
                }
            ]
        }
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout=json.dumps(ffprobe_output),
                stderr='',
                returncode=0
            )
            
            # Act
            metadata = await validator.validate_file(test_file, 2500, 10800)
            
            # Assert
            assert metadata['duration'] == 120.5
            assert metadata['has_video'] is True
            assert metadata['has_audio'] is True
            assert metadata['video_codec'] == 'h264'
            assert metadata['audio_codec'] == 'aac'
    
    @pytest.mark.asyncio
    async def test_validate_duration_exceeds_maximum(self, validator, tmp_path):
        """Testa erro quando duração excede máximo."""
        # Arrange
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"x" * 1000)
        
        ffprobe_output = {
            'format': {'duration': '12000', 'size': '1000'},
            'streams': []
        }
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout=json.dumps(ffprobe_output),
                returncode=0
            )
            
            # Act & Assert
            with pytest.raises(ValidationError, match="exceeds maximum"):
                await validator.validate_file(test_file, 2500, 10800)
    
    @pytest.mark.asyncio
    async def test_ffprobe_timeout(self, validator, tmp_path):
        """Testa timeout do FFprobe."""
        # Arrange
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"x" * 1000)
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired('ffprobe', 30)
            
            # Act & Assert
            with pytest.raises(InvalidVideoFileError, match="timed out"):
                await validator.validate_file(test_file, 2500, 10800)
    
    @pytest.mark.asyncio
    async def test_ffprobe_invalid_json(self, validator, tmp_path):
        """Testa JSON inválido do FFprobe."""
        # Arrange
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"x" * 1000)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout="invalid json{",
                returncode=0
            )
            
            # Act & Assert
            with pytest.raises(InvalidVideoFileError, match="invalid JSON"):
                await validator.validate_file(test_file, 2500, 10800)
