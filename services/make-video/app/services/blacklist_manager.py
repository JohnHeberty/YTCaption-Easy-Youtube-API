"""
Blacklist Manager - Gerenciamento de vídeos reprovados

Impede reprocessamento de vídeos que foram rejeitados na validação.
"""

import logging
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class BlacklistManager:
    """
    Gerencia blacklist de vídeos reprovados
    
    Armazena vídeos que foram rejeitados (COM legendas detectadas)
    para evitar reprocessamento.
    
    Usa SQLite via blacklist_factory ou fallback para arquivo JSON.
    """
    
    def __init__(self, db_path: str = "data/raw/shorts/blacklist.db"):
        self.db_path = Path(db_path)
        self.json_path = Path("data/raw/shorts/blacklist.json")
        
        # Criar diretório se não existir
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Por enquanto, usar JSON simples
        # TODO: Integrar com SQLiteBlacklist do blacklist_factory
        self._ensure_json()
    
    def _ensure_json(self):
        """Garantir que arquivo JSON existe"""
        if not self.json_path.exists():
            self.json_path.write_text(json.dumps({}))
    
    def _load_blacklist(self) -> Dict:
        """Carregar blacklist do JSON"""
        try:
            return json.loads(self.json_path.read_text())
        except Exception as e:
            logger.error(f"Erro ao carregar blacklist: {e}")
            return {}
    
    def _save_blacklist(self, blacklist: Dict):
        """Salvar blacklist no JSON"""
        try:
            self.json_path.write_text(json.dumps(blacklist, indent=2))
        except Exception as e:
            logger.error(f"Erro ao salvar blacklist: {e}")
    
    async def is_blacklisted(self, video_id: str) -> bool:
        """
        Verificar se vídeo está blacklisted
        
        Args:
            video_id: ID do vídeo
        
        Returns:
            True se blacklisted, False caso contrário
        """
        blacklist = self._load_blacklist()
        return video_id in blacklist
    
    async def add(self, video_id: str, reason: str = "", metadata: Optional[Dict] = None):
        """
        Adicionar vídeo ao blacklist
        
        Args:
            video_id: ID do vídeo
            reason: Motivo da rejeição
            metadata: Metadados adicionais
        """
        blacklist = self._load_blacklist()
        
        blacklist[video_id] = {
            'video_id': video_id,
            'reason': reason,
            'blacklisted_at': datetime.utcnow().isoformat(),
            'metadata': metadata or {}
        }
        
        self._save_blacklist(blacklist)
        logger.info(f"⚫ Blacklisted: {video_id} - {reason}")
    
    async def remove(self, video_id: str):
        """
        Remover vídeo do blacklist
        
        Args:
            video_id: ID do vídeo
        """
        blacklist = self._load_blacklist()
        
        if video_id in blacklist:
            del blacklist[video_id]
            self._save_blacklist(blacklist)
            logger.info(f"✅ Removed from blacklist: {video_id}")
    
    async def get_all(self) -> Dict:
        """
        Obter todos os vídeos blacklisted
        
        Returns:
            Dict com todos os vídeos blacklisted
        """
        return self._load_blacklist()
    
    async def count(self) -> int:
        """
        Contar vídeos blacklisted
        
        Returns:
            Número de vídeos blacklisted
        """
        return len(self._load_blacklist())
