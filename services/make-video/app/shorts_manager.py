"""
Shorts Cache Manager

Gerencia cache LOCAL de shorts baixados via video-downloader API.
NÃO baixa vídeos diretamente - apenas armazena e reutiliza.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ShortsCache:
    """Gerencia cache LOCAL de shorts já baixados via video-downloader.
    
    NÃO baixa vídeos diretamente - apenas armazena resultado de 
    chamadas à API do video-downloader para reutilização.
    """
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = self._load_metadata()
        
        logger.info(f"💾 Shorts cache initialized: {self.cache_dir}")
        logger.info(f"📊 Current cache size: {len(self.metadata)} shorts")
    
    def _load_metadata(self) -> Dict:
        """Carrega metadata do cache"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading metadata: {e}")
                return {}
        return {}
    
    def _save_metadata(self):
        """Salva metadata do cache"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
    
    def get(self, video_id: str) -> Optional[Dict]:
        """Retorna metadata se short existe em cache LOCAL
        
        Args:
            video_id: ID do vídeo
        
        Returns:
            Metadata do short ou None
        """
        if video_id in self.metadata:
            short = self.metadata[video_id]
            
            # Verificar se arquivo ainda existe
            file_path = Path(short["file_path"])
            if not file_path.exists():
                logger.warning(f"⚠️ Cache inconsistente: {video_id} no metadata mas arquivo não existe")
                del self.metadata[video_id]
                self._save_metadata()
                return None
            
            # Atualizar estatísticas de uso
            short["last_used"] = datetime.utcnow().isoformat()
            short["usage_count"] = short.get("usage_count", 0) + 1
            self._save_metadata()
            
            logger.info(f"✅ Cache HIT: {video_id} (usado {short['usage_count']} vezes)")
            return short
        
        logger.info(f"❌ Cache MISS: {video_id}")
        return None
    
    def add(self, video_id: str, file_path: str, metadata: Dict):
        """Adiciona short ao cache LOCAL (após download via video-downloader API)
        
        Args:
            video_id: ID do vídeo
            file_path: Caminho do arquivo local
            metadata: Metadados adicionais (duration, resolution, etc)
        """
        self.metadata[video_id] = {
            "video_id": video_id,
            "file_path": file_path,
            "downloaded_at": datetime.utcnow().isoformat(),
            "downloaded_via": "video-downloader-api",  # Origem: API externa
            "last_used": datetime.utcnow().isoformat(),
            "usage_count": 1,
            **metadata
        }
        self._save_metadata()
        
        logger.info(f"💾 Short adicionado ao cache: {video_id}")
    
    def remove(self, video_id: str) -> bool:
        """Remove short do cache (usado quando detectado com legendas)
        
        Args:
            video_id: ID do vídeo
        
        Returns:
            True se removido, False se não existia
        """
        if video_id in self.metadata:
            # Remover do metadata
            del self.metadata[video_id]
            self._save_metadata()
            
            logger.info(f"🗑️ Short removido do cache: {video_id}")
            return True
        
        return False
    
    def exists(self, video_id: str) -> bool:
        """Verifica se short existe no cache
        
        Args:
            video_id: ID do vídeo
        
        Returns:
            True se existe, False caso contrário
        """
        return video_id in self.metadata
    
    def get_path(self, video_id: str) -> Path:
        """Retorna o caminho onde um short será/está armazenado
        
        Args:
            video_id: ID do vídeo
        
        Returns:
            Path do arquivo de vídeo
        """
        return self.cache_dir / f"{video_id}.mp4"
    
    def get_cache_stats(self) -> Dict:
        """Retorna estatísticas do cache"""
        if not self.metadata:
            return {
                "total_shorts": 0,
                "total_size_bytes": 0,
                "total_size_gb": 0,
                "oldest_short": None,
                "newest_short": None,
                "most_used": None,
            }
        
        # Calcular tamanho total
        total_size = 0
        for short in self.metadata.values():
            file_path = Path(short["file_path"])
            if file_path.exists():
                total_size += file_path.stat().st_size
        
        # Encontrar mais usado
        most_used = max(
            self.metadata.values(),
            key=lambda s: s.get("usage_count", 0)
        )
        
        # Ordenar por data
        sorted_by_date = sorted(
            self.metadata.values(),
            key=lambda s: s["downloaded_at"]
        )
        
        return {
            "total_shorts": len(self.metadata),
            "total_size_bytes": total_size,
            "total_size_gb": round(total_size / (1024**3), 2),
            "oldest_short": sorted_by_date[0]["downloaded_at"] if sorted_by_date else None,
            "newest_short": sorted_by_date[-1]["downloaded_at"] if sorted_by_date else None,
            "most_used": {
                "video_id": most_used["video_id"],
                "usage_count": most_used.get("usage_count", 0)
            }
        }
    
    def cleanup_old(self, days: int = 30) -> int:
        """Remove shorts não usados há X dias
        
        Args:
            days: Número de dias de inatividade
        
        Returns:
            Número de shorts removidos
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        to_remove = []
        
        for video_id, short in self.metadata.items():
            last_used = datetime.fromisoformat(short["last_used"])
            if last_used < cutoff:
                to_remove.append(video_id)
        
        removed_count = 0
        for video_id in to_remove:
            file_path = Path(self.metadata[video_id]["file_path"])
            if file_path.exists():
                try:
                    file_path.unlink()
                    logger.info(f"🗑️ Removed old short: {video_id}")
                    removed_count += 1
                except Exception as e:
                    logger.error(f"Error removing file {file_path}: {e}")
            
            del self.metadata[video_id]
        
        if removed_count > 0:
            self._save_metadata()
            logger.info(f"🧹 Cleanup: {removed_count} old shorts removed (>{days} days)")
        
        return removed_count
    
    def list_all(self) -> List[Dict]:
        """Lista todos os shorts no cache
        
        Returns:
            Lista de metadados dos shorts
        """
        return list(self.metadata.values())
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do cache (alias para get_cache_stats)
        
        Returns:
            Estatísticas do cache
        """
        stats = self.get_cache_stats()
        
        # Adicionar informações extras
        stats["cache_dir"] = str(self.cache_dir)
        
        return stats
