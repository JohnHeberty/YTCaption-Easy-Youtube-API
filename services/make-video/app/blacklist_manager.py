"""
Blacklist Manager

Gerencia lista negra de vídeos problemáticos usando Redis
"""

import logging
from typing import Optional, List
from datetime import timedelta
from app.metrics import blacklist_size

logger = logging.getLogger(__name__)


class BlacklistManager:
    """
    Gerencia blacklist de video IDs problemáticos
    
    Usa Redis com TTL para expiração automática
    """
    
    def __init__(self, redis_client, ttl_days: int = 7, prefix: str = "blacklist:"):
        """
        Args:
            redis_client: Cliente Redis (redis.Redis ou fakeredis.FakeRedis)
            ttl_days: Dias até expirar entrada (default: 7)
            prefix: Prefixo das keys no Redis
        """
        self.redis = redis_client
        self.ttl = timedelta(days=ttl_days)
        self.prefix = prefix
        
        logger.info(f"BlacklistManager initialized (TTL: {ttl_days} days)")
        
        # Atualizar métrica inicial
        self._update_metrics()
    
    def is_blacklisted(self, video_id: str) -> bool:
        """
        Verifica se vídeo está na blacklist
        
        Args:
            video_id: ID do vídeo (YouTube video ID)
        
        Returns:
            True se está na blacklist
        """
        key = self._make_key(video_id)
        exists = self.redis.exists(key) > 0
        
        logger.debug(f"Blacklist check: {video_id} -> {exists}")
        
        return exists
    
    def add_to_blacklist(
        self,
        video_id: str,
        reason: str = "unknown",
        metadata: Optional[dict] = None
    ) -> bool:
        """
        Adiciona vídeo à blacklist
        
        Args:
            video_id: ID do vídeo
            reason: Motivo (e.g., "no_audio", "ocr_failed", "corrupted")
            metadata: Dados adicionais (opcional)
        
        Returns:
            True se adicionado com sucesso
        """
        key = self._make_key(video_id)
        
        # Dados a armazenar
        data = {
            'video_id': video_id,
            'reason': reason
        }
        
        if metadata:
            # Filtrar chaves reservadas para evitar sobrescrita
            filtered_metadata = {
                k: v for k, v in metadata.items()
                if k not in ('video_id', 'reason')
            }
            data.update(filtered_metadata)
            
            # Log warning se houve filtragem
            if len(filtered_metadata) < len(metadata):
                logger.warning(
                    f"Filtered reserved keys from metadata: "
                    f"{set(metadata.keys()) - set(filtered_metadata.keys())}"
                )
        
        # Armazenar com TTL
        self.redis.hset(key, mapping=data)
        self.redis.expire(key, self.ttl)
        
        logger.info(f"✅ Added to blacklist: {video_id} (reason: {reason})")
        
        # Atualizar métrica
        self._update_metrics()
        
        return True
    
    def remove_from_blacklist(self, video_id: str) -> bool:
        """
        Remove vídeo da blacklist
        
        Args:
            video_id: ID do vídeo
        
        Returns:
            True se removido (existia)
        """
        key = self._make_key(video_id)
        deleted = self.redis.delete(key)
        
        if deleted:
            logger.info(f"Removed from blacklist: {video_id}")
        else:
            logger.debug(f"Not in blacklist: {video_id}")
        
        # Atualizar métrica
        self._update_metrics()
        
        return deleted > 0
    
    def get_blacklist_info(self, video_id: str) -> Optional[dict]:
        """
        Obtém informações de um vídeo blacklisted
        
        Args:
            video_id: ID do vídeo
        
        Returns:
            Dict com informações ou None se não está blacklisted
        """
        key = self._make_key(video_id)
        
        data = self.redis.hgetall(key)
        
        if not data:
            return None
        
        # Converter bytes para strings se necessário (Redis sem decode_responses)
        if data and isinstance(next(iter(data.keys())), bytes):
            return {k.decode('utf-8'): v.decode('utf-8') for k, v in data.items()}
        
        return data
    
    def list_blacklisted(self, limit: int = 100) -> List[str]:
        """
        Lista vídeos na blacklist
        
        Args:
            limit: Máximo de resultados
        
        Returns:
            Lista de video IDs
        """
        pattern = f"{self.prefix}*"
        keys = self.redis.keys(pattern)
        
        # Extrair video IDs dos keys
        video_ids = []
        for key in keys[:limit]:
            # Converter bytes para string se necessário
            if isinstance(key, bytes):
                key = key.decode('utf-8')
            video_ids.append(key.replace(self.prefix, ''))
        
        return video_ids
    
    def get_size(self) -> int:
        """
        Retorna tamanho da blacklist
        
        Returns:
            Número de vídeos blacklisted
        """
        pattern = f"{self.prefix}*"
        return len(self.redis.keys(pattern))
    
    def clear(self) -> int:
        """
        Limpa toda a blacklist (⚠️ usar com cuidado)
        
        Returns:
            Número de entradas removidas
        """
        pattern = f"{self.prefix}*"
        keys = self.redis.keys(pattern)
        
        if keys:
            deleted = self.redis.delete(*keys)
        else:
            deleted = 0
        
        logger.warning(f"⚠️ Blacklist cleared: {deleted} entries removed")
        
        # Atualizar métrica
        self._update_metrics()
        
        return deleted
    
    def _make_key(self, video_id: str) -> str:
        """Cria key do Redis para um video_id"""
        return f"{self.prefix}{video_id}"
    
    def _update_metrics(self):
        """Atualiza métrica Prometheus com tamanho da blacklist"""
        size = self.get_size()
        blacklist_size.set(size)
