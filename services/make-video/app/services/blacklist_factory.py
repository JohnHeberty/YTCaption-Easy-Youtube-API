"""
Blacklist Factory (LEGACY)
DEPRECATED: Use video_status_factory.py instead

Mantido para compatibilidade com código legado.
Redireciona para VideoStatusStore.
"""

from .video_status_factory import get_video_status_store
from common.log_utils import get_logger

logger = get_logger(__name__)

def get_blacklist():
    """
    LEGACY: Retorna VideoStatusStore (compatível com blacklist antiga)
    
    Returns:
        VideoStatusStore com interface compatível
    """
    logger.warning("⚠️  get_blacklist() is deprecated. Use get_video_status_store() instead.")
    return get_video_status_store()
