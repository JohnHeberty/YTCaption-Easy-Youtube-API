"""
Testes para app.blacklist_manager
"""

import pytest
from app.blacklist_manager import BlacklistManager


@pytest.fixture
def blacklist_manager(mock_redis):
    """BlacklistManager com Redis mockado"""
    return BlacklistManager(mock_redis, ttl_days=7)


def test_initialization(mock_redis):
    """Testa inicialização do BlacklistManager"""
    manager = BlacklistManager(mock_redis, ttl_days=14, prefix="test:")
    
    assert manager.ttl.days == 14
    assert manager.prefix == "test:"


def test_add_to_blacklist(blacklist_manager):
    """Testa adicionar vídeo à blacklist"""
    result = blacklist_manager.add_to_blacklist(
        'video123',
        reason='no_audio',
        metadata={'duration': '60'}
    )
    
    assert result is True
    assert blacklist_manager.is_blacklisted('video123')


def test_is_blacklisted_false(blacklist_manager):
    """Testa vídeo não blacklisted"""
    assert blacklist_manager.is_blacklisted('video999') is False


def test_remove_from_blacklist(blacklist_manager):
    """Testa remover vídeo da blacklist"""
    # Adicionar
    blacklist_manager.add_to_blacklist('video456', reason='corrupted')
    assert blacklist_manager.is_blacklisted('video456')
    
    # Remover
    removed = blacklist_manager.remove_from_blacklist('video456')
    assert removed is True
    assert not blacklist_manager.is_blacklisted('video456')


def test_remove_nonexistent(blacklist_manager):
    """Testa remover vídeo que não existe"""
    removed = blacklist_manager.remove_from_blacklist('video_inexistente')
    assert removed is False


def test_get_blacklist_info(blacklist_manager):
    """Testa obter informações de vídeo blacklisted"""
    blacklist_manager.add_to_blacklist(
        'video789',
        reason='ocr_failed',
        metadata={'confidence': '30'}
    )
    
    info = blacklist_manager.get_blacklist_info('video789')
    
    assert info is not None
    assert info['video_id'] == 'video789'
    assert info['reason'] == 'ocr_failed'
    assert info['confidence'] == '30'


def test_get_blacklist_info_none(blacklist_manager):
    """Testa obter info de vídeo não blacklisted"""
    info = blacklist_manager.get_blacklist_info('video_inexistente')
    assert info is None


def test_list_blacklisted(blacklist_manager):
    """Testa listar vídeos blacklisted"""
    # Adicionar alguns vídeos
    blacklist_manager.add_to_blacklist('video_a', reason='test')
    blacklist_manager.add_to_blacklist('video_b', reason='test')
    blacklist_manager.add_to_blacklist('video_c', reason='test')
    
    blacklisted = blacklist_manager.list_blacklisted(limit=10)
    
    assert len(blacklisted) == 3
    assert 'video_a' in blacklisted
    assert 'video_b' in blacklisted
    assert 'video_c' in blacklisted


def test_get_size(blacklist_manager):
    """Testa obter tamanho da blacklist"""
    assert blacklist_manager.get_size() == 0
    
    blacklist_manager.add_to_blacklist('video1', reason='test')
    assert blacklist_manager.get_size() == 1
    
    blacklist_manager.add_to_blacklist('video2', reason='test')
    assert blacklist_manager.get_size() == 2
    
    blacklist_manager.remove_from_blacklist('video1')
    assert blacklist_manager.get_size() == 1


def test_clear(blacklist_manager):
    """Testa limpar toda a blacklist"""
    # Adicionar vários vídeos
    for i in range(5):
        blacklist_manager.add_to_blacklist(f'video_{i}', reason='test')
    
    assert blacklist_manager.get_size() == 5
    
    # Limpar
    deleted = blacklist_manager.clear()
    
    assert deleted == 5
    assert blacklist_manager.get_size() == 0


def test_ttl_set_on_add(blacklist_manager, mock_redis):
    """Testa que TTL é definido ao adicionar"""
    blacklist_manager.add_to_blacklist('video_ttl', reason='test')
    
    # Verificar que expire foi chamado
    key = 'blacklist:video_ttl'
    # Mock Redis deve ter registrado a chamada de expire
    assert mock_redis.exists(key) > 0


def test_add_blacklist_metadata_reserved_keys(blacklist_manager):
    """Testa que chaves reservadas em metadata não sobrescrevem dados principais"""
    # Tentar sobrescrever video_id e reason via metadata
    blacklist_manager.add_to_blacklist(
        'test_video',
        reason='corrupted',
        metadata={
            'video_id': 'malicious_override',  # Deve ser filtrado
            'reason': 'malicious_reason',      # Deve ser filtrado
            'custom_field': 'allowed'
        }
    )
    
    info = blacklist_manager.get_blacklist_info('test_video')
    
    # video_id e reason não devem ter sido sobrescritos
    assert info['video_id'] == 'test_video'
    assert info['reason'] == 'corrupted'
    assert info['custom_field'] == 'allowed'
