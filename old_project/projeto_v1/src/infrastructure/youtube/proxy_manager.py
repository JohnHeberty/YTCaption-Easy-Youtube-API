"""
Proxy Manager - v3.0

Gerencia proxies para download do YouTube.
Suporta Tor, SOCKS5, HTTP proxies e rotação.
"""
import random
from typing import List, Optional
from loguru import logger


class ProxyManager:
    """
    Gerenciador de proxies customizados.
    
    Features:
    - Lista customizada de proxies
    - Rotação aleatória
    - Fallback sem proxy
    """
    
    def __init__(
        self,
        custom_proxies: Optional[List[str]] = None,
        enable_no_proxy: bool = True
    ):
        """
        Inicializa gerenciador de proxies.
        
        Args:
            custom_proxies: Lista customizada de proxies
            enable_no_proxy: Se True, inclui None (sem proxy) na rotação
        """
        self.enable_no_proxy = enable_no_proxy
        
        # Construir lista de proxies
        self.proxies: List[Optional[str]] = []
        
        if custom_proxies:
            self.proxies.extend(custom_proxies)
            logger.info(f"✅ Added {len(custom_proxies)} custom proxies")
        
        if enable_no_proxy:
            self.proxies.append(None)
            logger.info("✅ No-proxy option enabled")
        
        self.current_index = 0
        self.rotation_count = 0
        
        logger.info(
            f"ProxyManager initialized: "
            f"custom={len(custom_proxies) if custom_proxies else 0}, "
            f"total_options={len(self.proxies)}"
        )
    
    def get_random(self) -> Optional[str]:
        """
        Retorna proxy aleatório.
        
        Returns:
            str ou None: URL do proxy ou None (sem proxy)
        """
        if not self.proxies:
            return None
        
        proxy = random.choice(self.proxies)
        self.rotation_count += 1
        
        if proxy:
            logger.debug(f"🔄 Using proxy (random #{self.rotation_count}): {proxy}")
        else:
            logger.debug(f"🔄 Using no proxy (random #{self.rotation_count})")
        
        return proxy
    
    def get_next(self) -> Optional[str]:
        """
        Retorna próximo proxy (rotação sequencial).
        
        Returns:
            str ou None: URL do proxy ou None (sem proxy)
        """
        if not self.proxies:
            return None
        
        proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        self.rotation_count += 1
        
        if proxy:
            logger.debug(f"🔄 Using proxy (sequential #{self.rotation_count}): {proxy}")
        else:
            logger.debug(f"🔄 Using no proxy (sequential #{self.rotation_count})")
        
        return proxy
    

    
    def is_enabled(self) -> bool:
        """Verifica se há proxies disponíveis."""
        return len(self.proxies) > 0
    
    def get_stats(self) -> dict:
        """
        Retorna estatísticas de proxies.
        
        Returns:
            dict: Estatísticas
        """
        return {
            "custom_proxies_count": len([p for p in self.proxies if p]),
            "no_proxy_enabled": self.enable_no_proxy,
            "total_options": len(self.proxies),
            "rotation_count": self.rotation_count,
            "current_index": self.current_index
        }


# Instância global (singleton)
_proxy_manager: Optional[ProxyManager] = None


def get_proxy_manager(
    custom_proxies: Optional[List[str]] = None
) -> ProxyManager:
    """
    Retorna instância singleton do gerenciador de proxies.
    
    Args:
        custom_proxies: Lista customizada de proxies
        
    Returns:
        ProxyManager
    """
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager(custom_proxies)
    return _proxy_manager
