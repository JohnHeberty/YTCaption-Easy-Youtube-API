"""
Blacklist Factory (LEGACY)
DEPRECATED: Use video_status_factory.py instead

Mantido para compatibilidade com código legado.
Redireciona para VideoStatusStore.
"""

import logging
from .video_status_factory import get_video_status_store

logger = logging.getLogger(__name__)


def get_blacklist():
    """
    LEGACY: Retorna VideoStatusStore (compatível com blacklist antiga)
    
    Returns:
        VideoStatusStore com interface compatível
    """
    logger.warning("⚠️  get_blacklist() is deprecated. Use get_video_status_store() instead.")
    return get_video_status_store()
