"""
Unit tests for Checkpoint Manager

Tests checkpoint save/load/resume functionality.
"""

import pytest
import json
import sys
import os

# Adicionar o caminho do app ao sys.path
app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', 'app'))
if app_path not in sys.path:
    sys.path.insert(0, app_path)

# Import direto do módulo para evitar app/__init__.py
from infrastructure.checkpoint_manager import (
    CheckpointManager,
    TranscriptionStage,
    CheckpointData
)


# Stub para RedisJobStore (sem Mock)
class StubRedisJobStore:
    """Stub para RedisJobStore"""
    def __init__(self):
        self.redis = StubRedis()


class StubRedis:
    """Stub para cliente Redis"""
    def __init__(self):
        self.data = {}
    
    def setex(self, key, ttl, value):
        self.data[key] = value
        return True
    
    def get(self, key):
        return self.data.get(key)
    
    def delete(self, key):
        self.data.pop(key, None)
        return True
    
    def keys(self, pattern):
        # Simple pattern matching
        prefix = pattern.replace('*', '')
        return [k.encode() for k in self.data.keys() if k.startswith(prefix)]


@pytest.fixture
def stub_redis_store():
    """Stub RedisJobStore"""
    return StubRedisJobStore()


@pytest.fixture
def checkpoint_manager(stub_redis_store):
    """CheckpointManager com Redis stub"""
    return CheckpointManager(stub_redis_store)


def test_checkpoint_manager_initialization(checkpoint_manager):
    """CheckpointManager deve inicializar corretamente"""
    assert checkpoint_manager.checkpoint_interval_seconds == 300


def test_checkpoint_key_generation(checkpoint_manager):
    """Deve gerar chave Redis correta"""
    key = checkpoint_manager._checkpoint_key("job_123")
    assert key == "checkpoint:job_123"


@pytest.mark.asyncio
async def test_save_checkpoint(checkpoint_manager, stub_redis_store):
    """Deve salvar checkpoint no Redis"""
    job_id = "job_123"
    
    await checkpoint_manager.save_checkpoint(
        job_id=job_id,
        stage=TranscriptionStage.TRANSCRIBING,
        processed_seconds=150.0,
        total_seconds=300.0,
        segments_completed=15,
        metadata={"language": "pt", "model": "base"}
    )
    
    # Verifica se dados foram salvos
    key = "checkpoint:job_123"
    assert key in stub_redis_store.redis.data
    
    # Verifica dados salvos
    saved_data = json.loads(stub_redis_store.redis.data[key])
    assert saved_data['stage'] == 'transcribing'
    assert saved_data['progress'] == 0.5
    assert saved_data['processed_seconds'] == 150.0
    assert saved_data['total_seconds'] == 300.0
    assert saved_data['segments_completed'] == 15
    assert saved_data['metadata']['language'] == 'pt'


def test_get_checkpoint_exists(checkpoint_manager, stub_redis_store):
    """Deve recuperar checkpoint do Redis"""
    job_id = "job_123"
    
    # Salva checkpoint no stub Redis
    checkpoint_dict = {
        'stage': 'transcribing',
        'progress': 0.5,
        'processed_seconds': 150.0,
        'total_seconds': 300.0,
        'segments_completed': 15,
        'metadata': {},
        'timestamp': '2024-01-01T00:00:00'
    }
    stub_redis_store.redis.data["checkpoint:job_123"] = json.dumps(checkpoint_dict)
    
    # Get checkpoint
    checkpoint = checkpoint_manager.get_checkpoint(job_id)
    
    assert checkpoint is not None
    assert checkpoint.stage == 'transcribing'
    assert checkpoint.progress == 0.5
    assert checkpoint.processed_seconds == 150.0


def test_get_checkpoint_not_exists(checkpoint_manager, stub_redis_store):
    """Deve retornar None se checkpoint não existe"""
    checkpoint = checkpoint_manager.get_checkpoint("job_999")
    assert checkpoint is None


def test_get_checkpoint_corrupted(checkpoint_manager, stub_redis_store):
    """Deve retornar None se checkpoint está corrompido"""
    # Coloca dados inválidos no Redis
    stub_redis_store.redis.data["checkpoint:job_123"] = "invalid json"
    
    checkpoint = checkpoint_manager.get_checkpoint("job_123")
    assert checkpoint is None


def test_should_save_checkpoint_yes(checkpoint_manager):
    """Deve retornar True se passou o intervalo"""
    result = checkpoint_manager.should_save_checkpoint(
        job_id="job_123",
        processed_seconds=400.0,
        last_checkpoint_seconds=0.0
    )
    assert result is True


def test_should_save_checkpoint_no(checkpoint_manager):
    """Deve retornar False se não passou o intervalo"""
    result = checkpoint_manager.should_save_checkpoint(
        job_id="job_123",
        processed_seconds=100.0,
        last_checkpoint_seconds=0.0
    )
    assert result is False


def test_delete_checkpoint(checkpoint_manager, stub_redis_store):
    """Deve deletar checkpoint do Redis"""
    job_id = "job_123"
    
    # Adiciona checkpoint ao stub Redis
    stub_redis_store.redis.data["checkpoint:job_123"] = "some data"
    
    checkpoint_manager.delete_checkpoint(job_id)
    
    # Verifica que foi removido
    assert "checkpoint:job_123" not in stub_redis_store.redis.data


def test_list_checkpoints(checkpoint_manager, stub_redis_store):
    """Deve listar todos os checkpoints ativos"""
    # Adiciona checkpoints ao stub Redis
    stub_redis_store.redis.data["checkpoint:job_1"] = "data1"
    stub_redis_store.redis.data["checkpoint:job_2"] = "data2"
    stub_redis_store.redis.data["checkpoint:job_3"] = "data3"
    stub_redis_store.redis.data["other:key"] = "data4"  # Não deve aparecer
    
    job_ids = checkpoint_manager.list_checkpoints()
    
    assert len(job_ids) == 3
    assert "job_1" in job_ids
    assert "job_2" in job_ids
    assert "job_3" in job_ids
    assert "other" not in job_ids


@pytest.mark.asyncio
async def test_resume_from_checkpoint_exists(checkpoint_manager, stub_redis_store):
    """Deve resumir do checkpoint se existe"""
    job_id = "job_123"
    
    # Salva checkpoint no stub Redis
    checkpoint_dict = {
        'stage': 'transcribing',
        'progress': 0.5,
        'processed_seconds': 150.0,
        'total_seconds': 300.0,
        'segments_completed': 15,
        'metadata': {},
        'timestamp': '2024-01-01T00:00:00'
    }
    stub_redis_store.redis.data["checkpoint:job_123"] = json.dumps(checkpoint_dict)
    
    # Resume
    checkpoint = await checkpoint_manager.resume_from_checkpoint(job_id)
    
    assert checkpoint is not None
    assert checkpoint.progress == 0.5


@pytest.mark.asyncio
async def test_resume_from_checkpoint_not_exists(checkpoint_manager, stub_redis_store):
    """Deve retornar None se checkpoint não existe"""
    checkpoint = await checkpoint_manager.resume_from_checkpoint("job_999")
    assert checkpoint is None


def test_checkpoint_data_to_dict():
    """CheckpointData deve converter para dict"""
    checkpoint = CheckpointData(
        stage='transcribing',
        progress=0.5,
        processed_seconds=150.0,
        total_seconds=300.0,
        segments_completed=15,
        metadata={'test': 'value'},
        timestamp='2024-01-01T00:00:00'
    )
    
    data = checkpoint.to_dict()
    
    assert data['stage'] == 'transcribing'
    assert data['progress'] == 0.5
    assert data['metadata']['test'] == 'value'


def test_checkpoint_data_from_dict():
    """CheckpointData deve criar instância de dict"""
    data = {
        'stage': 'transcribing',
        'progress': 0.5,
        'processed_seconds': 150.0,
        'total_seconds': 300.0,
        'segments_completed': 15,
        'metadata': {},
        'timestamp': '2024-01-01T00:00:00'
    }
    
    checkpoint = CheckpointData.from_dict(data)
    
    assert checkpoint.stage == 'transcribing'
    assert checkpoint.progress == 0.5
    assert checkpoint.processed_seconds == 150.0
