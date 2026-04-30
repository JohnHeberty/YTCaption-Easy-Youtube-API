"""
Distributed Lock Manager for Make-Video Service.

Segue princípios SOLID:
- Single Responsibility: Gerencia apenas locks distribuídos
- Dependency Inversion: Usa Redis via injeção

CRÍTICO: Usa redis.from_url() em vez de parsing manual da URL.
"""

import shortuuid
from typing import Optional
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import redis.asyncio as aioredis
from common.datetime_utils import now_brazil
from common.log_utils import get_logger

logger = get_logger(__name__)

class DistributedLockManager:
    """
    Gerencia locks distribuídos via Redis.

    Usa redis.from_url() para parsing robusto da URL.
    NÃO usa parsing manual frágil.
    """

    def __init__(self, redis_url: str):
        """
        Initialize lock manager.

        Args:
            redis_url: Redis connection URL (e.g., redis://host:port/db)
        """
        self.redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None

        # Parse URL apenas para log/validação (não para conexão)
        try:
            parsed = urlparse(redis_url)
            logger.info(
                f"DistributedLockManager initialized: "
                f"host={parsed.hostname or 'localhost'}, "
                f"port={parsed.port or 6379}, "
                f"db={parsed.path.lstrip('/') or '0'}"
            )
        except Exception as e:
            logger.warning(f"Could not parse Redis URL for logging: {e}")

    async def _get_redis(self) -> aioredis.Redis:
        """Obtém ou cria cliente Redis async."""
        if self._redis is None:
            # Usar redis.from_url() - parsing robusto e confiável
            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10,
            )
        return self._redis

    async def acquire(
        self,
        lock_name: str,
        timeout_seconds: int = 3600,
    ) -> Optional[str]:
        """
        Adquire lock distribuído.

        Args:
            lock_name: Nome do lock
            timeout_seconds: TTL do lock

        Returns:
            Token do lock se adquirido, None se falhar
        """
        token = shortuuid.uuid()
        lock_key = f"lock:{lock_name}"

        try:
            redis = await self._get_redis()

            # Tentar adquirir lock (NX = only if not exists)
            acquired = await redis.set(lock_key, token, nx=True, ex=timeout_seconds)

            if acquired:
                logger.info(f"🔒 Lock acquired: {lock_name} (token={token[:8]}...)")
                return token
            else:
                # Lock já existe - verificar se é stale
                ttl = await redis.ttl(lock_key)
                if ttl == -1:  # No expiration (corrupted lock)
                    logger.warning(f"⚠️ Stale lock detected: {lock_name}, removing")
                    await redis.delete(lock_key)
                    # Tentar novamente
                    acquired = await redis.set(lock_key, token, nx=True, ex=timeout_seconds)
                    if acquired:
                        logger.info(f"🔒 Lock acquired after removing stale: {lock_name}")
                        return token

                logger.debug(f"🔒 Lock busy: {lock_name}")
                return None

        except Exception as e:
            logger.error(f"❌ Error acquiring lock {lock_name}: {e}")
            return None

    async def release(self, lock_name: str, token: str) -> bool:
        """
        Libera lock distribuído.

        Args:
            lock_name: Nome do lock
            token: Token do lock

        Returns:
            True se liberado, False caso contrário
        """
        lock_key = f"lock:{lock_name}"

        try:
            redis = await self._get_redis()

            # Verificar se ainda temos o lock
            current_token = await redis.get(lock_key)

            if current_token == token:
                await redis.delete(lock_key)
                logger.info(f"🔓 Lock released: {lock_name}")
                return True
            else:
                logger.warning(
                    f"⚠️ Lock token mismatch: {lock_name} "
                    f"(expected={token[:8]}..., got={current_token[:8] if current_token else 'None'}...)"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Error releasing lock {lock_name}: {e}")
            return False

    @asynccontextmanager
    async def acquire_lock(
        self,
        lock_name: str,
        timeout_seconds: int = 3600,
    ):
        """
        Context manager para lock distribuído.

        Args:
            lock_name: Nome do lock
            timeout_seconds: TTL do lock

        Yields:
            Token do lock se adquirido

        Raises:
            RuntimeError: Se não conseguir adquirir lock
        """
        token = await self.acquire(lock_name, timeout_seconds)

        if token is None:
            raise RuntimeError(
                f"Could not acquire lock: {lock_name}. "
                f"Another process may be holding it."
            )

        try:
            yield token
        finally:
            await self.release(lock_name, token)

    async def is_locked(self, lock_name: str) -> bool:
        """
        Verifica se lock está ativo.

        Args:
            lock_name: Nome do lock

        Returns:
            True se lock existe, False caso contrário
        """
        try:
            redis = await self._get_redis()
            lock_key = f"lock:{lock_name}"
            return await redis.exists(lock_key) > 0
        except Exception as e:
            logger.error(f"❌ Error checking lock {lock_name}: {e}")
            return False

    async def get_lock_ttl(self, lock_name: str) -> int:
        """
        Retorna TTL restante do lock.

        Args:
            lock_name: Nome do lock

        Returns:
            Segundos restantes, -1 se sem TTL, -2 se não existe
        """
        try:
            redis = await self._get_redis()
            lock_key = f"lock:{lock_name}"
            return await redis.ttl(lock_key)
        except Exception as e:
            logger.error(f"❌ Error getting lock TTL {lock_name}: {e}")
            return -2

    async def extend_lock(
        self,
        lock_name: str,
        token: str,
        additional_seconds: int,
    ) -> bool:
        """
        Estende TTL de lock existente.

        Args:
            lock_name: Nome do lock
            token: Token do lock
            additional_seconds: Segundos a adicionar

        Returns:
            True se estendido, False caso contrário
        """
        lock_key = f"lock:{lock_name}"

        try:
            redis = await self._get_redis()

            # Verificar ownership
            current_token = await redis.get(lock_key)
            if current_token != token:
                return False

            # Estender TTL
            current_ttl = await redis.ttl(lock_key)
            if current_ttl > 0:
                new_ttl = current_ttl + additional_seconds
                await redis.expire(lock_key, new_ttl)
                logger.debug(f"🔒 Lock extended: {lock_name} (+{additional_seconds}s)")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Error extending lock {lock_name}: {e}")
            return False

    async def close(self):
        """Fecha conexão Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("DistributedLockManager closed")
