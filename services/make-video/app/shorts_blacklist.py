"""
Shorts Blacklist Manager
Gerencia lista negra de vídeos com legendas embutidas
"""

import fcntl
import json
import os
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
import tempfile
import shutil

logger = logging.getLogger(__name__)


class ShortsBlacklist:
    """Gerencia blacklist de vídeos com legendas embutidas (file-based com fcntl)"""
    
    def __init__(self, blacklist_path: str, ttl_days: int = 90):
        """
        Args:
            blacklist_path: Caminho do arquivo JSON da blacklist
            ttl_days: Dias para expiração de entradas antigas
        """
        self.blacklist_path = Path(blacklist_path)
        self.ttl_days = ttl_days
        self.ttl_seconds = ttl_days * 86400
        self._last_mtime = 0.0
        self._cache: Dict[str, Dict] = {}
        
        # Criar diretório se não existir
        self.blacklist_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Criar arquivo vazio se não existir
        if not self.blacklist_path.exists():
            self._write_blacklist({})
            logger.info(f"✅ Blacklist created: {self.blacklist_path}")
        else:
            logger.info(f"✅ Blacklist loaded: {self.blacklist_path}")
    
    def add(self, video_id: str, reason: str, confidence: float, metadata: Optional[Dict] = None):
        """
        Adiciona vídeo à blacklist
        
        Args:
            video_id: ID do vídeo
            reason: Motivo (ex: "embedded_subtitles")
            confidence: Confiança da detecção (0-1)
            metadata: Metadados adicionais (opcional)
        """
        with self._lock():
            data = self._read_blacklist()
            
            data[video_id] = {
                "reason": reason,
                "confidence": float(confidence),
                "added_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=self.ttl_days)).isoformat(),
                "metadata": metadata or {}
            }
            
            self._write_blacklist(data)
            logger.info(f"🚫 Blacklisted: {video_id} ({reason}, conf: {confidence:.2f})")
    
    def is_blacklisted(self, video_id: str) -> bool:
        """Verifica se vídeo está na blacklist (com reload automático por mtime)"""
        # Reload se arquivo foi modificado
        try:
            current_mtime = self.blacklist_path.stat().st_mtime
            if current_mtime != self._last_mtime:
                with self._lock():
                    data = self._read_blacklist()
                    self._cache = data
                    self._last_mtime = current_mtime
        except FileNotFoundError:
            self._cache = {}
            self._last_mtime = 0.0
        
        if video_id not in self._cache:
            return False
        
        # Verificar TTL
        entry = self._cache[video_id]
        expires_at = datetime.fromisoformat(entry['expires_at'])
        
        if datetime.now(timezone.utc) > expires_at:
            # Expirado - remover
            logger.debug(f"🗑️ Blacklist entry expired: {video_id}")
            with self._lock():
                data = self._read_blacklist()
                if video_id in data:
                    del data[video_id]
                    self._write_blacklist(data)
            return False
        
        return True
    
    def get_entry(self, video_id: str) -> Optional[Dict]:
        """Retorna detalhes da entrada na blacklist"""
        with self._lock():
            data = self._read_blacklist()
            return data.get(video_id)
    
    def cleanup_expired(self) -> int:
        """Remove entradas expiradas da blacklist"""
        with self._lock():
            data = self._read_blacklist()
            now = datetime.now(timezone.utc)
            
            expired = [
                vid for vid, entry in data.items()
                if datetime.fromisoformat(entry['expires_at']) < now
            ]
            
            for vid in expired:
                del data[vid]
            
            if expired:
                self._write_blacklist(data)
                logger.info(f"🗑️ Cleaned up {len(expired)} expired blacklist entries")
            
            return len(expired)
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas da blacklist"""
        with self._lock():
            data = self._read_blacklist()
            
            reasons = {}
            for entry in data.values():
                reason = entry['reason']
                reasons[reason] = reasons.get(reason, 0) + 1
            
            return {
                "total": len(data),
                "reasons": reasons,
                "ttl_days": self.ttl_days
            }
    
    def _lock(self):
        """Context manager para file locking"""
        class FileLock:
            def __init__(self, path):
                self.path = path
                self.lockfile = None
            
            def __enter__(self):
                # Criar lockfile
                lockpath = str(self.path) + '.lock'
                self.lockfile = open(lockpath, 'w')
                fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_EX)
                return self
            
            def __exit__(self, *args):
                if self.lockfile:
                    fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_UN)
                    self.lockfile.close()
        
        return FileLock(self.blacklist_path)
    
    def _read_blacklist(self) -> Dict:
        """Lê blacklist do disco"""
        try:
            with open(self.blacklist_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _write_blacklist(self, data: Dict):
        """Escreve blacklist no disco (atomic write)"""
        # Atomic write via temp file + rename
        with tempfile.NamedTemporaryFile(
            mode='w',
            dir=self.blacklist_path.parent,
            delete=False
        ) as tmp:
            json.dump(data, tmp, indent=2)
            tmp_path = tmp.name
        
        shutil.move(tmp_path, self.blacklist_path)
        self._last_mtime = self.blacklist_path.stat().st_mtime
