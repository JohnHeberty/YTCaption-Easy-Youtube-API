"""
Blacklist Factory
Cria instância de blacklist SQLite permanente
"""

import logging

from app.core.config import get_settings
from .sqlite_blacklist import SQLiteBlacklist

logger = logging.getLogger(__name__)


class BlacklistFactory:
    """Factory simplificada para criar instância de blacklist SQLite"""
    
    @staticmethod
    def create() -> SQLiteBlacklist:
        """
        Cria instância de SQLiteBlacklist permanente
        
        Returns:
            Instância de SQLiteBlacklist
            
        Raises:
            RuntimeError: Se falhar ao criar instância
        """
        config = get_settings()
        db_path = config.get(\"sqlite_db_path\", \"./raw/shorts/blacklist.db\")
        
        logger.info(f"🏭 Creating SQLite blacklist: {db_path}")
        
        try:
            blacklist = SQLiteBlacklist(db_path=db_path)
            logger.info(f"✅ SQLiteBlacklist created successfully")
            return blacklist
            
        except Exception as e:
            logger.error(f"❌ Failed to create SQLiteBlacklist: {e}")
            raise RuntimeError(f"Failed to initialize blacklist: {e}")


# Singleton global para reutilização
_blacklist_instance = None


def get_blacklist() -> SQLiteBlacklist:
    """
    Retorna instância singleton de blacklist
    
    Returns:
        Instância de SQLiteBlacklist
    """
    global _blacklist_instance
    
    if _blacklist_instance is None:
        _blacklist_instance = BlacklistFactory.create()
    
    return _blacklist_instance
