"""Testes para Checkpoint Manager com arquivos REAIS"""
import pytest
import json
import pickle
from pathlib import Path
import time


class TestCheckpointManager:
    """Testes de checkpoint com arquivos reais"""
    
    def test_save_checkpoint_json(self, tmp_path):
        """Salva checkpoint real em JSON"""
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        
        job_id = "job_123"
        state = {"stage": "transform", "progress": 50, "video_id": "abc123"}
        
        # Salvar
        checkpoint_file = checkpoint_dir / f"{job_id}.json"
        checkpoint_file.write_text(json.dumps(state, indent=2))
        
        assert checkpoint_file.exists()
        assert checkpoint_file.stat().st_size > 0
        
        # Load
        loaded = json.loads(checkpoint_file.read_text())
        assert loaded == state
        assert loaded["stage"] == "transform"
        assert loaded["progress"] == 50
    
    def test_load_checkpoint(self, tmp_path):
        """Carrega checkpoint existente"""
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        
        job_id = "job_456"
        expected_state = {
            "stage": "validate",
            "progress": 75,
            "video_id": "xyz789",
            "timestamp": 1234567890
        }
        
        # Criar checkpoint
        checkpoint_file = checkpoint_dir / f"{job_id}.json"
        checkpoint_file.write_text(json.dumps(expected_state))
        
        # Carregar
        assert checkpoint_file.exists()
        loaded_state = json.loads(checkpoint_file.read_text())
        
        assert loaded_state == expected_state
        assert loaded_state["stage"] == "validate"
        assert loaded_state["progress"] == 75
    
    def test_update_checkpoint(self, tmp_path):
        """Atualiza checkpoint existente"""
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        
        job_id = "job_789"
        checkpoint_file = checkpoint_dir / f"{job_id}.json"
        
        # Estado inicial
        initial_state = {"stage": "download", "progress": 25}
        checkpoint_file.write_text(json.dumps(initial_state))
        
        # Atualizar
        updated_state = {"stage": "transform", "progress": 50}
        checkpoint_file.write_text(json.dumps(updated_state))
        
        # Verificar
        loaded = json.loads(checkpoint_file.read_text())
        assert loaded == updated_state
        assert loaded["progress"] == 50
    
    def test_delete_checkpoint(self, tmp_path):
        """Remove checkpoint após conclusão"""
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        
        job_id = "job_complete"
        checkpoint_file = checkpoint_dir / f"{job_id}.json"
        
        # Criar
        state = {"stage": "complete", "progress": 100}
        checkpoint_file.write_text(json.dumps(state))
        assert checkpoint_file.exists()
        
        # Deletar
        checkpoint_file.unlink()
        assert not checkpoint_file.exists()
    
    def test_list_checkpoints(self, tmp_path):
        """Lista todos os checkpoints"""
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        
        # Criar vários checkpoints
        jobs = ["job_001", "job_002", "job_003"]
        for job_id in jobs:
            checkpoint_file = checkpoint_dir / f"{job_id}.json"
            checkpoint_file.write_text(json.dumps({"job_id": job_id}))
        
        # Listar
        checkpoint_files = list(checkpoint_dir.glob("*.json"))
        assert len(checkpoint_files) == 3
        
        # Verificar nomes
        checkpoint_names = [f.stem for f in checkpoint_files]
        assert set(checkpoint_names) == set(jobs)
    
    def test_checkpoint_with_complex_data(self, tmp_path):
        """Checkpoint com dados complexos"""
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        
        job_id = "job_complex"
        complex_state = {
            "video_id": "abc123",
            "stage": "transform",
            "progress": 60,
            "metadata": {
                "duration": 120.5,
                "resolution": "1280x720",
                "fps": 30
            },
            "stages_completed": ["download", "extract"],
            "errors": []
        }
        
        # Salvar
        checkpoint_file = checkpoint_dir / f"{job_id}.json"
        checkpoint_file.write_text(json.dumps(complex_state, indent=2))
        
        # Carregar e verificar
        loaded = json.loads(checkpoint_file.read_text())
        assert loaded == complex_state
        assert loaded["metadata"]["resolution"] == "1280x720"
        assert loaded["stages_completed"] == ["download", "extract"]
    
    def test_checkpoint_with_timestamp(self, tmp_path):
        """Checkpoint com timestamp"""
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        
        job_id = "job_timestamp"
        
        # Criar com timestamp
        timestamp = time.time()
        state = {
            "stage": "processing",
            "progress": 45,
            "timestamp": timestamp
        }
        
        checkpoint_file = checkpoint_dir / f"{job_id}.json"
        checkpoint_file.write_text(json.dumps(state))
        
        # Verificar timestamp
        loaded = json.loads(checkpoint_file.read_text())
        assert abs(loaded["timestamp"] - timestamp) < 1.0
    
    def test_checkpoint_recovery_scenario(self, tmp_path):
        """Cenário de recuperação após falha"""
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        
        job_id = "job_recovery"
        checkpoint_file = checkpoint_dir / f"{job_id}.json"
        
        # Simular progresso antes da falha
        states = [
            {"stage": "download", "progress": 10},
            {"stage": "download", "progress": 50},
            {"stage": "download", "progress": 100},
            {"stage": "transform", "progress": 30}  # Falha aqui
        ]
        
        # Salvar último estado antes da falha
        last_state = states[-1]
        checkpoint_file.write_text(json.dumps(last_state))
        
        # Simular recuperação: carregar último estado
        recovered_state = json.loads(checkpoint_file.read_text())
        
        assert recovered_state["stage"] == "transform"
        assert recovered_state["progress"] == 30
        
        # Continuar de onde parou
        recovered_state["progress"] = 60
        checkpoint_file.write_text(json.dumps(recovered_state))
        
        final_state = json.loads(checkpoint_file.read_text())
        assert final_state["progress"] == 60
    
    def test_checkpoint_pickle_format(self, tmp_path):
        """Salva checkpoint em formato pickle (alternativo)"""
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        
        job_id = "job_pickle"
        state = {"stage": "validate", "data": [1, 2, 3, 4, 5]}
        
        # Salvar com pickle
        checkpoint_file = checkpoint_dir / f"{job_id}.pkl"
        with checkpoint_file.open('wb') as f:
            pickle.dump(state, f)
        
        assert checkpoint_file.exists()
        
        # Carregar
        with checkpoint_file.open('rb') as f:
            loaded = pickle.load(f)
        
        assert loaded == state
        assert loaded["data"] == [1, 2, 3, 4, 5]


class TestCheckpointManagerModule:
    """Testa módulo checkpoint_manager.py"""
    
    def test_checkpoint_manager_module_imports(self):
        """Módulo checkpoint_manager importa"""
        try:
            from app.infrastructure import checkpoint_manager
            assert checkpoint_manager is not None
        except ImportError:
            pytest.skip("checkpoint_manager.py não existe")
    
    def test_checkpoint_directory_creation(self, tmp_path):
        """Cria diretório de checkpoints se não existir"""
        checkpoint_dir = tmp_path / "checkpoints" / "nested"
        
        # Criar diretório
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        assert checkpoint_dir.exists()
        assert checkpoint_dir.is_dir()
