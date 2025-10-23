"""
Testes unitários para Local Storage Service.
"""
import pytest
import tempfile
from pathlib import Path
from src.infrastructure.storage.local_storage import LocalStorageService


class TestLocalStorageService:
    """Testes para serviço de storage local."""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Cria diretório temporário para testes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def storage_service(self, temp_storage_dir):
        """Cria instância do storage service."""
        return LocalStorageService(base_path=temp_storage_dir)
    
    def test_save_file(self, storage_service, temp_storage_dir):
        """Deve salvar arquivo no storage."""
        content = b"Test file content"
        file_name = "test.txt"
        
        saved_path = storage_service.save(file_name, content)
        
        assert saved_path.exists()
        assert saved_path.read_bytes() == content
    
    def test_save_creates_subdirectories(self, storage_service):
        """Deve criar subdiretórios automaticamente."""
        content = b"Test content"
        file_path = "subdir/nested/file.txt"
        
        saved_path = storage_service.save(file_path, content)
        
        assert saved_path.exists()
        assert saved_path.parent.name == "nested"
    
    def test_delete_file(self, storage_service):
        """Deve deletar arquivo do storage."""
        # Salvar arquivo primeiro
        content = b"To be deleted"
        file_name = "delete_me.txt"
        saved_path = storage_service.save(file_name, content)
        
        assert saved_path.exists()
        
        # Deletar
        storage_service.delete(file_name)
        
        assert not saved_path.exists()
    
    def test_exists_returns_true_for_existing_file(self, storage_service):
        """Deve retornar True para arquivo existente."""
        content = b"Exists"
        file_name = "exists.txt"
        storage_service.save(file_name, content)
        
        assert storage_service.exists(file_name)
    
    def test_exists_returns_false_for_missing_file(self, storage_service):
        """Deve retornar False para arquivo não existente."""
        assert not storage_service.exists("non_existent.txt")
    
    def test_get_file_path(self, storage_service, temp_storage_dir):
        """Deve retornar path completo do arquivo."""
        file_name = "test.txt"
        
        path = storage_service.get_path(file_name)
        
        assert isinstance(path, Path)
        assert path.parent == temp_storage_dir
        assert path.name == file_name
    
    def test_list_files(self, storage_service):
        """Deve listar arquivos no storage."""
        # Salvar alguns arquivos
        storage_service.save("file1.txt", b"Content 1")
        storage_service.save("file2.txt", b"Content 2")
        storage_service.save("subdir/file3.txt", b"Content 3")
        
        files = storage_service.list_files()
        
        assert len(files) >= 2
        file_names = [f.name for f in files]
        assert "file1.txt" in file_names
        assert "file2.txt" in file_names
