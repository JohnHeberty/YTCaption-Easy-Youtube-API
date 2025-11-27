"""
Testes para RvcModelManager
Sprint 6 - Model Management (Red Phase)
"""
import pytest
from pathlib import Path
import torch
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.rvc_model_manager import RvcModelManager
from app.models import RvcModel
from app.exceptions import RvcModelException, RvcModelNotFoundException


class TestRvcModelManagerInitialization:
    """Testes de inicialização do RvcModelManager"""
    
    def test_init_creates_storage_dir(self, tmp_path):
        """Deve criar diretório de storage se não existir"""
        storage_dir = tmp_path / "rvc_models"
        assert not storage_dir.exists()
        
        manager = RvcModelManager(storage_dir=str(storage_dir))
        
        assert storage_dir.exists()
        assert storage_dir.is_dir()
    
    def test_init_empty_models_dict(self, tmp_path):
        """Deve inicializar com dicionário vazio de modelos"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        models = manager.list_models()
        assert len(models) == 0
    
    def test_init_loads_existing_models(self, tmp_path):
        """Deve carregar modelos existentes no diretório"""
        storage_dir = tmp_path / "models"
        storage_dir.mkdir()
        
        # Cria modelo fake
        model_path = storage_dir / "test_model.pth"
        torch.save({'weight': {}}, model_path)
        
        manager = RvcModelManager(storage_dir=str(storage_dir))
        
        # Deve detectar modelo existente
        # (implementação pode variar)


class TestRvcModelManagerUpload:
    """Testes de upload de modelos"""
    
    @pytest.mark.asyncio
    async def test_upload_model_success(self, tmp_path):
        """Deve fazer upload de modelo com sucesso"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        # Cria arquivo .pth fake
        pth_file = tmp_path / "upload" / "voice.pth"
        pth_file.parent.mkdir(parents=True)
        torch.save({'weight': {}, 'params': {}}, pth_file)
        
        # Upload
        model = await manager.upload_model(
            name="Test Voice",
            pth_file=pth_file,
            index_file=None,
            description="Test model"
        )
        
        assert model is not None
        assert model.name == "Test Voice"
        assert model.id is not None
        assert Path(model.pth_path).exists()
    
    @pytest.mark.asyncio
    async def test_upload_model_with_index(self, tmp_path):
        """Deve fazer upload com arquivo .index"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        pth_file = tmp_path / "voice.pth"
        index_file = tmp_path / "voice.index"
        
        torch.save({'weight': {}}, pth_file)
        index_file.write_text("fake index")
        
        model = await manager.upload_model(
            name="Voice with Index",
            pth_file=pth_file,
            index_file=index_file
        )
        
        assert model.index_path is not None
        assert Path(model.index_path).exists()
    
    @pytest.mark.asyncio
    async def test_upload_model_invalid_pth(self, tmp_path):
        """Deve rejeitar arquivo .pth inválido"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        # Arquivo não é PyTorch válido
        pth_file = tmp_path / "invalid.pth"
        pth_file.write_text("not a torch file")
        
        with pytest.raises(RvcModelException, match="invalid"):
            await manager.upload_model(
                name="Invalid",
                pth_file=pth_file
            )
    
    @pytest.mark.asyncio
    async def test_upload_model_file_not_found(self, tmp_path):
        """Deve falhar se arquivo não existir"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        fake_path = tmp_path / "nonexistent.pth"
        
        with pytest.raises(RvcModelException, match="not found"):
            await manager.upload_model(
                name="Missing",
                pth_file=fake_path
            )
    
    @pytest.mark.asyncio
    async def test_upload_model_duplicate_name(self, tmp_path):
        """Deve permitir nomes duplicados (IDs diferentes)"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        pth_file = tmp_path / "voice.pth"
        torch.save({'weight': {}}, pth_file)
        
        model1 = await manager.upload_model("Same Name", pth_file)
        model2 = await manager.upload_model("Same Name", pth_file)
        
        assert model1.id != model2.id
        assert model1.name == model2.name


class TestRvcModelManagerList:
    """Testes de listagem de modelos"""
    
    @pytest.mark.asyncio
    async def test_list_models_empty(self, tmp_path):
        """Deve retornar lista vazia se não há modelos"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        models = manager.list_models()
        
        assert isinstance(models, list)
        assert len(models) == 0
    
    @pytest.mark.asyncio
    async def test_list_models_with_data(self, tmp_path):
        """Deve listar modelos existentes"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        # Upload 3 modelos
        pth_file = tmp_path / "voice.pth"
        torch.save({'weight': {}}, pth_file)
        
        await manager.upload_model("Voice 1", pth_file)
        await manager.upload_model("Voice 2", pth_file)
        await manager.upload_model("Voice 3", pth_file)
        
        models = manager.list_models()
        
        assert len(models) == 3
        assert all(isinstance(m, RvcModel) for m in models)
    
    def test_list_models_sorted_by_created_at(self, tmp_path):
        """Deve ordenar modelos por data de criação (mais recente primeiro)"""
        # Implementação depende de ordenação escolhida
        pass


class TestRvcModelManagerGet:
    """Testes de busca de modelo por ID"""
    
    @pytest.mark.asyncio
    async def test_get_model_success(self, tmp_path):
        """Deve retornar modelo existente"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        pth_file = tmp_path / "voice.pth"
        torch.save({'weight': {}}, pth_file)
        
        uploaded = await manager.upload_model("Test", pth_file)
        
        retrieved = manager.get_model(uploaded.id)
        
        assert retrieved is not None
        assert retrieved.id == uploaded.id
        assert retrieved.name == uploaded.name
    
    def test_get_model_not_found(self, tmp_path):
        """Deve lançar exceção se modelo não existir"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        with pytest.raises(RvcModelNotFoundException):
            manager.get_model("nonexistent_id")
    
    def test_get_model_none_id(self, tmp_path):
        """Deve rejeitar ID None"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        with pytest.raises(ValueError):
            manager.get_model(None)


class TestRvcModelManagerDelete:
    """Testes de deleção de modelos"""
    
    @pytest.mark.asyncio
    async def test_delete_model_success(self, tmp_path):
        """Deve deletar modelo e arquivos"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        pth_file = tmp_path / "voice.pth"
        torch.save({'weight': {}}, pth_file)
        
        model = await manager.upload_model("To Delete", pth_file)
        model_id = model.id
        
        # Verifica que existe
        assert manager.get_model(model_id) is not None
        
        # Deleta
        success = await manager.delete_model(model_id)
        
        assert success is True
        
        # Verifica que não existe mais
        with pytest.raises(RvcModelNotFoundException):
            manager.get_model(model_id)
    
    @pytest.mark.asyncio
    async def test_delete_model_removes_files(self, tmp_path):
        """Deve remover arquivos .pth e .index"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        pth_file = tmp_path / "voice.pth"
        index_file = tmp_path / "voice.index"
        
        torch.save({'weight': {}}, pth_file)
        index_file.write_text("index")
        
        model = await manager.upload_model("Test", pth_file, index_file)
        
        pth_path = Path(model.pth_path)
        index_path = Path(model.index_path)
        
        assert pth_path.exists()
        assert index_path.exists()
        
        await manager.delete_model(model.id)
        
        assert not pth_path.exists()
        assert not index_path.exists()
    
    @pytest.mark.asyncio
    async def test_delete_model_not_found(self, tmp_path):
        """Deve retornar False se modelo não existir"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        success = await manager.delete_model("nonexistent")
        
        assert success is False


class TestRvcModelManagerValidation:
    """Testes de validação de modelos"""
    
    def test_validate_model_valid_pth(self, tmp_path):
        """Deve validar arquivo .pth correto"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        pth_file = tmp_path / "valid.pth"
        torch.save({'weight': {}, 'config': {}}, pth_file)
        
        is_valid = manager.validate_model_file(pth_file)
        
        assert is_valid is True
    
    def test_validate_model_invalid_format(self, tmp_path):
        """Deve rejeitar arquivo não-PyTorch"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        pth_file = tmp_path / "invalid.pth"
        pth_file.write_text("not torch")
        
        is_valid = manager.validate_model_file(pth_file)
        
        assert is_valid is False
    
    def test_validate_model_missing_keys(self, tmp_path):
        """Deve validar estrutura do modelo"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        pth_file = tmp_path / "incomplete.pth"
        torch.save({}, pth_file)  # Sem 'weight'
        
        # Pode aceitar ou rejeitar dependendo de validação
        # Teste deve documentar comportamento esperado


class TestRvcModelManagerStorage:
    """Testes de persistência"""
    
    @pytest.mark.asyncio
    async def test_storage_persists_across_instances(self, tmp_path):
        """Modelos devem persistir entre instâncias"""
        storage_dir = tmp_path / "storage"
        
        # Primeira instância: cria modelo
        manager1 = RvcModelManager(storage_dir=str(storage_dir))
        pth_file = tmp_path / "voice.pth"
        torch.save({'weight': {}}, pth_file)
        
        model = await manager1.upload_model("Persistent", pth_file)
        model_id = model.id
        
        # Segunda instância: deve carregar modelo
        manager2 = RvcModelManager(storage_dir=str(storage_dir))
        
        retrieved = manager2.get_model(model_id)
        
        assert retrieved is not None
        assert retrieved.id == model_id
    
    @pytest.mark.asyncio
    async def test_concurrent_access_safety(self, tmp_path):
        """Deve lidar com acesso concurrent (se aplicável)"""
        # Teste de thread-safety se necessário
        pass


class TestRvcModelManagerEdgeCases:
    """Testes de edge cases"""
    
    @pytest.mark.asyncio
    async def test_very_large_model_file(self, tmp_path):
        """Deve lidar com arquivos grandes"""
        # Simula modelo grande (ex: 500MB)
        # Teste pode ser marcado como @slow
        pass
    
    @pytest.mark.asyncio
    async def test_special_characters_in_name(self, tmp_path):
        """Deve aceitar caracteres especiais em nome"""
        manager = RvcModelManager(storage_dir=str(tmp_path))
        
        pth_file = tmp_path / "voice.pth"
        torch.save({'weight': {}}, pth_file)
        
        special_names = [
            "Voice (Test)",
            "Voice-123",
            "Voice_2024",
            "José's Voice",
            "声音模型"
        ]
        
        for name in special_names:
            model = await manager.upload_model(name, pth_file)
            assert model.name == name
    
    @pytest.mark.asyncio
    async def test_max_models_limit(self, tmp_path):
        """Deve impor limite máximo de modelos (se aplicável)"""
        # Se houver limite configurável
        pass
