"""
Testes para factory pattern
Red phase: Todos devem FALHAR (factory não existe)
"""
import pytest
from unittest.mock import patch, MagicMock
from app.engines.factory import (
    create_engine,
    create_engine_with_fallback,
    clear_engine_cache,
    _ENGINE_CACHE
)
from app.engines.base import TTSEngine
from app.exceptions import TTSEngineException


def test_create_engine_xtts(settings):
    """Factory cria engine XTTS"""
    engine = create_engine('xtts', settings)
    
    assert engine is not None
    assert engine.engine_name == 'xtts'
    assert isinstance(engine, TTSEngine)


def test_create_engine_f5tts(settings):
    """Factory cria engine F5-TTS"""
    engine = create_engine('f5tts', settings)
    
    assert engine is not None
    assert engine.engine_name == 'f5tts'
    assert isinstance(engine, TTSEngine)


def test_create_engine_invalid(settings):
    """Factory levanta erro para engine inválido"""
    with pytest.raises(ValueError, match="Unknown engine type"):
        create_engine('invalid_engine', settings)


def test_create_engine_caches_instances(settings):
    """Factory cacheia engines (singleton)"""
    clear_engine_cache()  # Limpa cache
    
    engine1 = create_engine('xtts', settings)
    engine2 = create_engine('xtts', settings)
    
    assert engine1 is engine2  # Mesma instância


def test_create_engine_force_recreate(settings):
    """Factory recria engine quando force_recreate=True"""
    clear_engine_cache()
    
    engine1 = create_engine('xtts', settings)
    engine2 = create_engine('xtts', settings, force_recreate=True)
    
    assert engine1 is not engine2  # Instâncias diferentes


def test_create_engine_with_fallback_success(settings):
    """Fallback retorna engine primário quando sucesso"""
    clear_engine_cache()
    engine = create_engine_with_fallback('xtts', settings)
    assert engine.engine_name == 'xtts'


def test_create_engine_with_fallback_to_xtts(settings):
    """Fallback usa XTTS quando F5-TTS falha"""
    clear_engine_cache()
    
    with patch('app.engines.factory.F5TtsEngine', side_effect=Exception("F5-TTS error")):
        engine = create_engine_with_fallback('f5tts', settings, fallback_engine='xtts')
        assert engine.engine_name == 'xtts'  # Fallback


def test_create_engine_with_fallback_all_fail(settings):
    """Fallback levanta erro quando todos engines falham"""
    clear_engine_cache()
    
    with patch('app.engines.factory.XttsEngine', side_effect=Exception("XTTS error")):
        with pytest.raises(TTSEngineException, match="All engines failed"):
            create_engine_with_fallback('xtts', settings)


def test_clear_engine_cache_specific():
    """Limpa cache de engine específico"""
    # Mock cache
    _ENGINE_CACHE['xtts'] = MagicMock()
    _ENGINE_CACHE['f5tts'] = MagicMock()
    
    clear_engine_cache('xtts')
    
    assert 'xtts' not in _ENGINE_CACHE
    assert 'f5tts' in _ENGINE_CACHE


def test_clear_engine_cache_all():
    """Limpa todo cache"""
    _ENGINE_CACHE['xtts'] = MagicMock()
    _ENGINE_CACHE['f5tts'] = MagicMock()
    
    clear_engine_cache()
    
    assert len(_ENGINE_CACHE) == 0


def test_create_engine_uses_correct_config(settings):
    """Factory passa config correta para cada engine"""
    clear_engine_cache()
    
    with patch('app.engines.factory.XttsEngine') as mock_xtts:
        mock_instance = MagicMock()
        mock_instance.engine_name = 'xtts'
        mock_xtts.return_value = mock_instance
        
        create_engine('xtts', settings)
        
        # Verifica que XttsEngine foi chamado com params corretos
        mock_xtts.assert_called_once()
        call_kwargs = mock_xtts.call_args[1]
        assert call_kwargs['device'] == 'cpu'
        assert call_kwargs['fallback_to_cpu'] is True


def test_create_engine_logs_cache_hit(settings, caplog):
    """Factory loga quando usa cache"""
    clear_engine_cache()
    
    # Primeira chamada - cria engine
    engine1 = create_engine('xtts', settings)
    
    # Segunda chamada - usa cache
    import logging
    with caplog.at_level(logging.INFO):
        engine2 = create_engine('xtts', settings)
    
    assert "Using cached engine: xtts" in caplog.text
    assert engine1 is engine2


def test_create_engine_handles_initialization_error(settings):
    """Factory captura erros de inicialização e levanta TTSEngineException"""
    clear_engine_cache()
    
    with patch('app.engines.factory.XttsEngine', side_effect=RuntimeError("GPU not available")):
        with pytest.raises(TTSEngineException, match="Engine initialization failed"):
            create_engine('xtts', settings)
