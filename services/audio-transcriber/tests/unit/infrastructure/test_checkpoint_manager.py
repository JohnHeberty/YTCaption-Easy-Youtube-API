"""
Unit tests for Checkpoint Manager

Tests checkpoint save/load/resume functionality.
"""

import pytest
import json
import sys
import os
from unittest.mock import Mock, MagicMock

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


@pytest.fixture
def mock_redis_store():
    """Mock RedisJobStore"""
    store = Mock()
    store.redis = Mock()
    return store


@pytest.fixture
def checkpoint_manager(mock_redis_store):
    """CheckpointManager com Redis mockado"""
    return CheckpointManager(mock_redis_store)


def test_checkpoint_manager_initialization(checkpoint_manager):
    """CheckpointManager deve inicializar corretamente"""
    assert checkpoint_manager.checkpoint_interval_seconds == 300


def test_checkpoint_key_generation(checkpoint_manager):
    """Deve gerar chave Redis correta"""
    key = checkpoint_manager._checkpoint_key("job_123")
    assert key == "checkpoint:job_123"


@pytest.mark.asyncio
async def test_save_checkpoint(checkpoint_manager, mock_redis_store):
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
    
    # Verifica se setex foi chamado
    mock_redis_store.redis.setex.assert_called_once()
    
    # Verifica argumentos
    args = mock_redis_store.redis.setex.call_args[0]
    assert args[0] == "checkpoint:job_123"  # key
    assert args[1] == 86400  # TTL
    
    # Verifica dados salvos
    saved_data = json.loads(args[2])
    assert saved_data['stage'] == 'transcribing'
    assert saved_data['progress'] == 0.5
    assert saved_data['processed_seconds'] == 150.0
    assert saved_data['total_seconds'] == 300.0
    assert saved_data['segments_completed'] == 15
    assert saved_data['metadata']['language'] == 'pt'


def test_get_checkpoint_exists(checkpoint_manager, mock_redis_store):
    """Deve recuperar checkpoint do Redis"""
    job_id = "job_123"
    
    # Mock Redis get
    checkpoint_dict = {
        'stage': 'transcribing',
        'progress': 0.5,
        'processed_seconds': 150.0,
        'total_seconds': 300.0,
        'segments_completed': 15,
        'metadata': {},
        'timestamp': '2024-01-01T00:00:00'
    }
    mock_redis_store.redis.get.return_value = json.dumps(checkpoint_dict)
    
    # Get checkpoint
    checkpoint = checkpoint_manager.get_checkpoint(job_id)
    
    assert checkpoint is not None
    assert checkpoint.stage == 'transcribing'
    assert checkpoint.progress == 0.5
    assert checkpoint.processed_seconds == 150.0


def test_get_checkpoint_not_exists(checkpoint_manager, mock_redis_store):
    """Deve retornar None se checkpoint não existe"""
    mock_redis_store.redis.get.return_value = None
    
    checkpoint = checkpoint_manager.get_checkpoint("job_999")
    assert checkpoint is None


def test_get_checkpoint_corrupted(checkpoint_manager, mock_redis_store):
    """Deve retornar None se checkpoint está corrompido"""
    mock_redis_store.redis.get.return_value = "invalid json"
    
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


def test_delete_checkpoint(checkpoint_manager, mock_redis_store):
    """Deve deletar checkpoint do Redis"""
    job_id = "job_123"
    
    checkpoint_manager.delete_checkpoint(job_id)
    
    mock_redis_store.redis.delete.assert_called_once_with("checkpoint:job_123")


def test_list_checkpoints(checkpoint_manager, mock_redis_store):
    """Deve listar todos os checkpoints ativos"""
    # Mock Redis keys
    mock_redis_store.redis.keys.return_value = [
        b"checkpoint:job_1",
        b"checkpoint:job_2",
        b"checkpoint:job_3"
    ]
    
    job_ids = checkpoint_manager.list_checkpoints()
    
    assert len(job_ids) == 3
    assert "job_1" in job_ids
    assert "job_2" in job_ids
    assert "job_3" in job_ids


@pytest.mark.asyncio
async def test_resume_from_checkpoint_exists(checkpoint_manager, mock_redis_store):
    """Deve resumir do checkpoint se existe"""
    job_id = "job_123"
    
    # Mock checkpoint existente
    checkpoint_dict = {
        'stage': 'transcribing',
        'progress': 0.5,
        'processed_seconds': 150.0,
        'total_seconds': 300.0,
        'segments_completed': 15,
        'metadata': {},
        'timestamp': '2024-01-01T00:00:00'
    }
    mock_redis_store.redis.get.return_value = json.dumps(checkpoint_dict)
    
    # Resume
    checkpoint = await checkpoint_manager.resume_from_checkpoint(job_id)
    
    assert checkpoint is not None
    assert checkpoint.progress == 0.5


@pytest.mark.asyncio
async def test_resume_from_checkpoint_not_exists(checkpoint_manager, mock_redis_store):
    """Deve retornar None se checkpoint não existe"""
    mock_redis_store.redis.get.return_value = None
    
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
