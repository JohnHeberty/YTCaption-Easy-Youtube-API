"""
Blacklist Manager - Gerenciamento de vídeos reprovados

Impede reprocessamento de vídeos que foram rejeitados na validação.
Usa VideoStatusStore (SQLite) para persistência eficiente com ACID.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
import json

from .video_status_factory import get_video_status_store

logger = logging.getLogger(__name__)


class BlacklistManager:
    """
    Gerencia blacklist de vídeos reprovados
    
    Armazena vídeos que foram rejeitados (COM legendas detectadas)
    para evitar reprocessamento.
    
    Usa VideoStatusStore (SQLite) com:
    - Transações ACID
    - Concorrência nativa (WAL mode)
    - Performance superior ao JSON
    - Histórico permanente
    """
    
    def __init__(self, db_path: str = "data/database/video_status.db"):
        """
        Inicializa BlacklistManager com SQLite backend
        
        Args:
            db_path: Caminho do banco SQLite (padrão: data/database/video_status.db)
        """
        self.db_path = Path(db_path)
        self.json_path = Path("data/raw/shorts/blacklist.json")  # Legacy path
        
        # Usar VideoStatusStore (singleton)
        self.store = get_video_status_store()
        
        # Migrar dados legados do JSON se existir
        self._migrate_from_json_if_needed()
        
        logger.info(f"✅ BlacklistManager initialized with SQLite: {db_path}")
    
    def _migrate_from_json_if_needed(self):
        """
        Migra dados do JSON legado para SQLite (executa apenas uma vez)
        
        Verifica se existe JSON antigo e migra para o novo sistema.
        """
        if not self.json_path.exists():
            logger.debug("No legacy JSON blacklist found, skipping migration")
            return
        
        try:
            # Carregar blacklist legada
            legacy_data = json.loads(self.json_path.read_text())
            
            if not legacy_data:
                logger.debug("Legacy JSON blacklist is empty, skipping migration")
                return
            
            # Migrar cada entrada
            migrated_count = 0
            for video_id, entry in legacy_data.items():
                # Verificar se já existe no novo sistema
                if self.store.is_rejected(video_id):
                    continue
                
                # Migrar com dados preservados
                reason = entry.get('reason', 'legacy_blacklist')
                metadata = entry.get('metadata', {})
                metadata['migrated_from_json'] = True
                metadata['original_blacklisted_at'] = entry.get('blacklisted_at', '')
                
                self.store.add_rejected(
                    video_id=video_id,
                    reason=reason,
                    confidence=0.95,  # Assume alta confiança (já estava blacklisted)
                    metadata=metadata
                )
                migrated_count += 1
            
            if migrated_count > 0:
                logger.info(f"✅ Migrated {migrated_count} entries from JSON to SQLite")
                
                # Fazer backup do JSON antigo
                backup_path = self.json_path.with_suffix('.json.bak')
                self.json_path.rename(backup_path)
                logger.info(f"📦 Legacy JSON backup created: {backup_path}")
            
        except Exception as e:
            logger.error(f"⚠️ Failed to migrate legacy JSON blacklist: {e}")
            # Não falhar - sistema continua funcionando
    
    async def is_blacklisted(self, video_id: str) -> bool:
        """
        Verificar se vídeo está blacklisted
        
        Args:
            video_id: ID do vídeo
        
        Returns:
            True se blacklisted, False caso contrário
        """
        return self.store.is_rejected(video_id)
    
    async def add(self, video_id: str, reason: str = "", metadata: Optional[Dict] = None):
        """
        Adicionar vídeo ao blacklist
        
        Args:
            video_id: ID do vídeo
            reason: Motivo da rejeição
            metadata: Metadados adicionais
        """
        # Default confidence for manual blacklist additions
        confidence = metadata.get('confidence', 0.95) if metadata else 0.95
        
        self.store.add_rejected(
            video_id=video_id,
            reason=reason or 'manual_blacklist',
            confidence=confidence,
            metadata=metadata
        )
        
        logger.info(f"⚫ Blacklisted: {video_id} - {reason}")
    
    async def remove(self, video_id: str):
        """
        Remover vídeo do blacklist
        
        Args:
            video_id: ID do vídeo
            
        Note:
            Remove da tabela rejected_videos no SQLite
        """
        try:
            with self.store._get_conn() as conn:
                result = conn.execute(
                    "DELETE FROM rejected_videos WHERE video_id = ?",
                    (video_id,)
                )
                
                if result.rowcount > 0:
                    logger.info(f"✅ Removed from blacklist: {video_id}")
                else:
                    logger.warning(f"⚠️ Video not in blacklist: {video_id}")
                    
        except Exception as e:
            logger.error(f"❌ Failed to remove from blacklist: {e}")
            raise
    
    async def get_all(self) -> List[Dict]:
        """
        Obter todos os vídeos blacklisted
        
        Returns:
            Lista de dicionários com todos os vídeos blacklisted
        """
        # Retorna todos (sem paginação)
        return self.store.list_rejected(limit=10000, offset=0)
    
    async def count(self) -> int:
        """
        Contar vídeos blacklisted
        
        Returns:
            Número de vídeos blacklisted
        """
        return self.store.count_rejected()
