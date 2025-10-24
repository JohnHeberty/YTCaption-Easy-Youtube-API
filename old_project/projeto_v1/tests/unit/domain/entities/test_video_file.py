"""
Testes unitários para a entidade VideoFile.
"""
import pytest
from pathlib import Path
from datetime import datetime
from src.domain.entities.video_file import VideoFile


class TestVideoFile:
    """Testes para a entidade VideoFile."""
    
    def test_create_video_file_with_defaults(self):
        """Deve criar VideoFile com valores padrão."""
        video = VideoFile()
        
        assert video.id is not None
        assert isinstance(video.id, str)
        assert isinstance(video.file_path, Path)
        assert video.file_path == Path()
        assert video.original_url is None
        assert video.file_size_bytes == 0
        assert video.format is None
        assert isinstance(video.created_at, datetime)
    
    def test_create_video_file_with_all_fields(self):
        """Deve criar VideoFile com todos os campos."""
        file_path = Path("/tmp/test_video.mp4")
        
        video = VideoFile(
            file_path=file_path,
            original_url="https://youtube.com/watch?v=test",
            file_size_bytes=1024 * 1024 * 50,  # 50 MB
            format="mp4"
        )
        
        assert isinstance(video.file_path, Path)
        assert video.file_path == file_path
        assert video.original_url == "https://youtube.com/watch?v=test"
        assert video.file_size_bytes == 1024 * 1024 * 50
        assert video.format == "mp4"
    
    def test_file_path_string_conversion(self):
        """Deve converter string para Path automaticamente."""
        video = VideoFile(file_path="/tmp/video.mp4")
        
        assert isinstance(video.file_path, Path)
        assert video.file_path == Path("/tmp/video.mp4")
    
    def test_file_size_mb_property(self):
        """Deve calcular tamanho em MB corretamente."""
        video = VideoFile(file_size_bytes=1024 * 1024 * 10)  # 10 MB
        
        assert video.file_size_mb == 10.0
    
    def test_extension_property(self):
        """Deve retornar extensão do arquivo."""
        video = VideoFile(file_path=Path("/tmp/test.mp4"))
        
        assert video.extension == ".mp4"
    
    def test_exists_property(self, tmp_path):
        """Deve verificar se arquivo existe."""
        # Arquivo que não existe
        video1 = VideoFile(file_path=Path("/tmp/nonexistent.mp4"))
        assert not video1.exists
        
        # Arquivo que existe
        test_file = tmp_path / "test.mp4"
        test_file.write_text("test content")
        
        video2 = VideoFile(file_path=test_file)
        assert video2.exists
    
    def test_delete_existing_file(self, tmp_path):
        """Deve deletar arquivo existente."""
        test_file = tmp_path / "test_delete.mp4"
        test_file.write_text("test content")
        
        video = VideoFile(file_path=test_file)
        assert video.exists
        
        result = video.delete()
        
        assert result is True
        assert not test_file.exists()
    
    def test_delete_nonexistent_file(self):
        """Deve retornar False ao tentar deletar arquivo que não existe."""
        video = VideoFile(file_path=Path("/tmp/nonexistent.mp4"))
        
        result = video.delete()
        
        assert result is False
    
    def test_to_dict(self):
        """Deve converter para dicionário."""
        video = VideoFile(
            file_path=Path("/tmp/test.mp4"),
            original_url="https://youtube.com/watch?v=abc",
            file_size_bytes=1024 * 1024 * 25,  # 25 MB
            format="mp4"
        )
        
        data = video.to_dict()
        
        assert data["id"] == video.id
        assert Path(data["file_path"]) == Path("/tmp/test.mp4")  # Platform-independent path check
        assert data["original_url"] == "https://youtube.com/watch?v=abc"
        assert data["file_size_mb"] == 25.0
        assert data["format"] == "mp4"
        assert "created_at" in data
        assert "exists" in data
