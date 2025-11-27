"""
Factory for creating TTS engines with singleton caching

This module implements the Factory pattern with singleton caching to efficiently
manage TTS engine instances. It supports multiple engines (XTTS, F5-TTS) and 
provides graceful fallback mechanisms.

Key Features:
    - Singleton caching: Engines are created once and reused
    - Lazy imports: Engine modules loaded only when needed
    - Graceful fallback: Automatic fallback to XTTS if requested engine fails
    - Easy testing: Cache can be cleared for unit tests

Example:
    >>> from app.engines.factory import create_engine
    >>> settings = {'tts_engines': {'xtts': {'device': 'cuda'}}}
    >>> engine = create_engine('xtts', settings)
    >>> audio, duration = await engine.generate_dubbing("Hello", "en")

Author: Audio Voice Service Team
Date: November 27, 2025
Sprint: 1 - Multi-Engine Foundation
"""
import logging
from typing import Dict, Optional, Type
from .base import TTSEngine
from ..exceptions import TTSEngineException

logger = logging.getLogger(__name__)

# Singleton cache to avoid recreating engines
_ENGINE_CACHE: Dict[str, TTSEngine] = {}

# Engine registry for lazy loading (populated on first use)
_ENGINE_REGISTRY: Dict[str, Optional[Type[TTSEngine]]] = {
    'xtts': None,   # Loaded lazily: XttsEngine
    'f5tts': None   # Loaded lazily: F5TtsEngine
}


def create_engine(
    engine_type: str,
    settings: dict,
    force_recreate: bool = False
) -> TTSEngine:
    """
    Factory method to create TTS engines with caching.
    
    Args:
        engine_type: Engine identifier ('xtts', 'f5tts')
        settings: Application settings dict
        force_recreate: If True, recreate even if cached
    
    Returns:
        TTSEngine: Engine instance (cached or new)
    
    Raises:
        ValueError: If engine_type unknown
        TTSEngineException: If engine initialization fails
    """
    # Check cache
    if not force_recreate and engine_type in _ENGINE_CACHE:
        logger.info(f"Using cached engine: {engine_type}")
        return _ENGINE_CACHE[engine_type]
    
    logger.info(f"Creating new engine: {engine_type}")
    
    try:
        # Lazy load engine class if not already loaded
        if engine_type == 'xtts':
            if _ENGINE_REGISTRY['xtts'] is None:
                from .xtts_engine import XttsEngine
                _ENGINE_REGISTRY['xtts'] = XttsEngine
            
            engine_class = _ENGINE_REGISTRY['xtts']
            xtts_config = settings.get('tts_engines', {}).get('xtts', {})
            engine = engine_class(
                device=xtts_config.get('device'),
                fallback_to_cpu=xtts_config.get('fallback_to_cpu', True),
                model_name=xtts_config.get('model_name', 'tts_models/multilingual/multi-dataset/xtts_v2')
            )
        elif engine_type == 'f5tts':
            if _ENGINE_REGISTRY['f5tts'] is None:
                from .f5tts_engine import F5TtsEngine
                _ENGINE_REGISTRY['f5tts'] = F5TtsEngine
            
            engine_class = _ENGINE_REGISTRY['f5tts']
            f5tts_config = settings.get('tts_engines', {}).get('f5tts', {})
            engine = engine_class(
                device=f5tts_config.get('device'),
                fallback_to_cpu=f5tts_config.get('fallback_to_cpu', True),
                model_name=f5tts_config.get('model_name', 'SWivid/F5-TTS')
            )
        else:
            raise ValueError(
                f"Unknown engine type: {engine_type}. "
                f"Supported: {', '.join(_ENGINE_REGISTRY.keys())}"
            )
        
        # Cache engine
        _ENGINE_CACHE[engine_type] = engine
        logger.info(f"✅ Engine {engine_type} created and cached")
        
        return engine
    
    except Exception as e:
        logger.error(f"Failed to create engine {engine_type}: {e}", exc_info=True)
        raise TTSEngineException(
            f"Engine initialization failed: {engine_type}"
        ) from e


def create_engine_with_fallback(
    engine_type: str,
    settings: dict,
    fallback_engine: str = 'xtts'
) -> TTSEngine:
    """
    Create engine with graceful fallback to default.
    
    Args:
        engine_type: Desired engine type
        settings: Application settings
        fallback_engine: Fallback engine if primary fails (default: xtts)
    
    Returns:
        TTSEngine: Primary or fallback engine
    
    Raises:
        TTSEngineException: If all engines fail
    """
    try:
        return create_engine(engine_type, settings)
    except Exception as e:
        if engine_type != fallback_engine:
            logger.warning(
                f"Failed to load {engine_type}, falling back to {fallback_engine}: {e}"
            )
            try:
                return create_engine(fallback_engine, settings)
            except Exception as fallback_error:
                logger.error(
                    f"Fallback engine {fallback_engine} also failed: {fallback_error}",
                    exc_info=True
                )
                raise TTSEngineException(
                    "All engines failed to initialize"
                ) from fallback_error
        else:
            raise TTSEngineException(
                f"Primary engine {engine_type} failed to initialize"
            ) from e


def clear_engine_cache(engine_type: Optional[str] = None):
    """
    Clear engine cache (useful for testing or reloading).
    
    Args:
        engine_type: Specific engine to clear, or None for all
    """
    global _ENGINE_CACHE
    
    if engine_type:
        if engine_type in _ENGINE_CACHE:
            del _ENGINE_CACHE[engine_type]
            logger.info(f"Cleared cache for engine: {engine_type}")
    else:
        _ENGINE_CACHE.clear()
        logger.info("Cleared all engine cache")
