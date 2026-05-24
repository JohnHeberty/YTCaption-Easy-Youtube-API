"""
Cache Manager for Make-Video Service.

Segue princípios SOLID:
- Single Responsibility: Gerencia apenas cache de shorts
- Interface Segregation: Implementa CacheManagerInterface
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import shutil

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

logger = get_logger(__name__)

class CacheManager:
    """
    Gerencia cache de shorts do YouTube.

    Responsabilidades:
    - Armazenar metadados de shorts
    - Rastrear uso de cache
    - Limpar cache antigo
    - Listar vídeos aprovados
    """

    def __init__(self, cache_dir: str):
        """
        Initialize cache manager.

        Args:
            cache_dir: Diretório raiz do cache
        """
        self.cache_dir = Path(cache_dir)
        self.approved_dir = Path("data/approved/videos")
        self.stats_file = self.cache_dir / "cache_stats.json"

        # Criar diretórios se não existirem
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.approved_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"CacheManager initialized: {self.cache_dir}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do cache.

        Returns:
            Dict com estatísticas
        """
        stats = {
            "total_shorts": 0,
            "total_size_mb": 0.0,
            "approved_videos": 0,
            "cache_dir": str(self.cache_dir),
        }

        try:
            # Contar shorts em cache
            if self.cache_dir.exists():
                for item in self.cache_dir.iterdir():
                    if item.is_file() and item.suffix == ".mp4":
                        stats["total_shorts"] += 1
                        stats["total_size_mb"] += item.stat().st_size / (1024 * 1024)

            # Contar vídeos aprovados
            if self.approved_dir.exists():
                stats["approved_videos"] = len(
                    list(self.approved_dir.glob("*.mp4"))
                )

            stats["total_size_mb"] = round(stats["total_size_mb"], 2)

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")

        return stats

    def cleanup_old(self, days: int = 30) -> int:
        """
        Remove shorts não usados há X dias.

        Args:
            days: Número de dias

        Returns:
            Número de shorts removidos
        """
        cutoff = now_brazil() - timedelta(days=days)
        removed_count = 0

        try:
            for item in self.cache_dir.iterdir():
                if not item.is_file():
                    continue

                # Verificar idade do arquivo
                mtime = datetime.fromtimestamp(item.stat().st_mtime)
                if mtime < cutoff:
                    try:
                        item.unlink()
                        removed_count += 1
                        logger.debug(f"Removed old cache file: {item.name}")
                    except Exception as e:
                        logger.warning(f"Failed to remove {item.name}: {e}")

            logger.info(f"Cache cleanup: {removed_count} old shorts removed")

        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")

        return removed_count

    def get_approved_videos(self) -> List[Path]:
        """
        Retorna lista de vídeos aprovados.

        Returns:
            Lista de Path para vídeos aprovados
        """
        if not self.approved_dir.exists():
            return []

        return list(self.approved_dir.glob("*.mp4"))

    def get_approved_video_ids(self) -> List[str]:
        """
        Retorna lista de IDs de vídeos aprovados.

        Returns:
            Lista de video IDs (nomes sem extensão)
        """
        videos = self.get_approved_videos()
        return [v.stem for v in videos]

    def is_video_approved(self, video_id: str) -> bool:
        """
        Verifica se vídeo está aprovado.

        Args:
            video_id: ID do vídeo

        Returns:
            True se aprovado, False caso contrário
        """
        approved_path = self.approved_dir / f"{video_id}.mp4"
        return approved_path.exists()

    def get_video_path(self, video_id: str) -> Optional[Path]:
        """
        Retorna path de vídeo aprovado.

        Args:
            video_id: ID do vídeo

        Returns:
            Path se existir, None caso contrário
        """
        approved_path = self.approved_dir / f"{video_id}.mp4"
        return approved_path if approved_path.exists() else None

    def clear_all(self) -> int:
        """
        Limpa TODO o cache (cuidado!).

        Returns:
            Número de arquivos removidos
        """
        removed = 0
        try:
            if self.cache_dir.exists():
                for item in self.cache_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                        removed += 1
                    elif item.is_dir():
                        shutil.rmtree(item)
                        removed += 1

            if self.approved_dir.exists():
                for item in self.approved_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                        removed += 1

            logger.warning(f"Cache cleared: {removed} items removed")

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

        return removed

    def get_cache_size_mb(self) -> float:
        """
        Retorna tamanho total do cache em MB.

        Returns:
            Tamanho em MB
        """
        total_bytes = 0
        try:
            if self.cache_dir.exists():
                for item in self.cache_dir.iterdir():
                    if item.is_file():
                        total_bytes += item.stat().st_size

            if self.approved_dir.exists():
                for item in self.approved_dir.iterdir():
                    if item.is_file():
                        total_bytes += item.stat().st_size

        except Exception as e:
            logger.error(f"Error calculating cache size: {e}")

        return round(total_bytes / (1024 * 1024), 2)
