"""
YouTube Download Configuration - v3.0

Configurações centralizadas para download resiliente.
"""
import os
from typing import Optional
from loguru import logger


class YouTubeDownloadConfig:
    """Configurações de download do YouTube."""
    
    def __init__(self):
        """Carrega configurações de variáveis de ambiente."""
        
        # Retry & Circuit Breaker
        self.max_retries = int(os.getenv("YOUTUBE_MAX_RETRIES", "5"))
        self.retry_delay_min = int(os.getenv("YOUTUBE_RETRY_DELAY_MIN", "10"))
        self.retry_delay_max = int(os.getenv("YOUTUBE_RETRY_DELAY_MAX", "120"))
        self.circuit_breaker_threshold = int(os.getenv("YOUTUBE_CIRCUIT_BREAKER_THRESHOLD", "8"))
        self.circuit_breaker_timeout = int(os.getenv("YOUTUBE_CIRCUIT_BREAKER_TIMEOUT", "180"))
        
        # Rate Limiting
        self.requests_per_minute = int(os.getenv("YOUTUBE_REQUESTS_PER_MINUTE", "10"))
        self.requests_per_hour = int(os.getenv("YOUTUBE_REQUESTS_PER_HOUR", "200"))
        self.cooldown_on_error = int(os.getenv("YOUTUBE_COOLDOWN_ON_ERROR", "60"))
        
        # Multi-Strategy
        self.enable_multi_strategy = os.getenv("ENABLE_MULTI_STRATEGY", "true").lower() == "true"
        
        # User-Agent Rotation
        self.enable_user_agent_rotation = os.getenv("ENABLE_USER_AGENT_ROTATION", "true").lower() == "true"
        
        # Timeout
        self.download_timeout = int(os.getenv("DOWNLOAD_TIMEOUT", "900"))
        
        self._log_config()
    
    def _log_config(self):
        """Loga configurações carregadas."""
        logger.info("=" * 60)
        logger.info("📋 YouTube Download Configuration (v3.0)")
        logger.info("=" * 60)
        logger.info(f"🔄 Retry: max={self.max_retries}, delay={self.retry_delay_min}-{self.retry_delay_max}s")
        logger.info(f"🔌 Circuit Breaker: threshold={self.circuit_breaker_threshold}, timeout={self.circuit_breaker_timeout}s")
        logger.info(f"⏱️  Rate Limit: {self.requests_per_minute}/min, {self.requests_per_hour}/hour, cooldown={self.cooldown_on_error}s")
        logger.info(f"🎯 Multi-Strategy: {self.enable_multi_strategy}")
        logger.info(f"🔄 User-Agent Rotation: {self.enable_user_agent_rotation}")
        logger.info(f"⏳ Download Timeout: {self.download_timeout}s")
        logger.info("=" * 60)


# Instância global (singleton)
_config: Optional[YouTubeDownloadConfig] = None


def get_youtube_config() -> YouTubeDownloadConfig:
    """
    Retorna instância singleton da configuração.
    
    Returns:
        YouTubeDownloadConfig
    """
    global _config
    if _config is None:
        _config = YouTubeDownloadConfig()
    return _config
