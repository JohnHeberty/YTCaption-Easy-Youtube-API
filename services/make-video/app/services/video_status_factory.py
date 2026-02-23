"""
Video Status Factory
Cria instância do VideoStatusStore (substitui blacklist_factory.py)
"""

import logging

from app.core.config import get_settings
from .video_status_store import VideoStatusStore

logger = logging.getLogger(__name__)


class VideoStatusFactory:
    """Factory para criar instância de VideoStatusStore"""
    
    @staticmethod
    def create() -> VideoStatusStore:
        """
        Cria instância de VideoStatusStore
        
        Returns:
            Instância de VideoStatusStore
            
        Raises:
            RuntimeError: Se falhar ao criar instância
        """
        config = get_settings()
        # NOVA LOCALIZAÇÃO: data/database/video_status.db
        db_path = config.get("video_status_db_path", "./data/database/video_status.db")
        
        logger.info(f"🏭 Creating VideoStatusStore: {db_path}")
        
        try:
            store = VideoStatusStore(db_path=db_path)
            logger.info(f"✅ VideoStatusStore created successfully")
            return store
            
        except Exception as e:
            logger.error(f"❌ Failed to create VideoStatusStore: {e}")
            raise RuntimeError(f"Failed to initialize video status store: {e}")


# Singleton global para reutilização
_status_store_instance = None


def get_video_status_store() -> VideoStatusStore:
    """
    Retorna instância singleton de VideoStatusStore
    
    Returns:
        Instância de VideoStatusStore
    """
    global _status_store_instance
    
    if _status_store_instance is None:
        _status_store_instance = VideoStatusFactory.create()
    
    return _status_store_instance


# Alias para compatibilidade com código legado
def get_blacklist() -> VideoStatusStore:
    """
    LEGACY: Alias para get_video_status_store()
    Mantido para compatibilidade com código existente
    """
    return get_video_status_store()
