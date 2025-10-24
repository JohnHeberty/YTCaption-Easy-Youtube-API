"""
User Agent Rotation - v3.1

Rotaciona User-Agents para evitar detecção de automação.
Usa fake-useragent + lista customizada carregada de arquivo.
"""
import random
from pathlib import Path
from typing import Optional
from loguru import logger

try:
    from fake_useragent import UserAgent
    HAS_FAKE_USERAGENT = True
except ImportError:
    HAS_FAKE_USERAGENT = False
    logger.warning("fake-useragent not installed, using static list only")

from .user_agent_loader import load_user_agents_from_file, get_default_user_agents_file


class UserAgentRotator:
    """
    Rotacionador de User-Agents.
    
    Combina fake-useragent (dinâmico) com lista customizada (fallback).
    """
    
    # Lista customizada de User-Agents (fallback se arquivo não existir)
    CUSTOM_USER_AGENTS = [
        # Desktop - Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        
        # Desktop - Firefox
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
        
        # Desktop - Edge
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        
        # Desktop - Safari
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        
        # Mobile - Chrome Android
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
        
        # Mobile - Safari iOS
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.6099.119 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
        
        # Tablet - Android
        "Mozilla/5.0 (Linux; Android 13; SM-X900) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        
        # Smart TV / Console
        "Mozilla/5.0 (PlayStation; PlayStation 5/6.00) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (Web0S; Linux/SmartTV) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.79 Safari/537.36",
    ]
    
    def _load_user_agents(self, user_agents_file: Optional[Path] = None) -> None:
        """
        Carrega user agents do arquivo ou usa lista hardcoded como fallback.
        
        Args:
            user_agents_file: Caminho customizado para o arquivo de user agents
        """
        # Determinar qual arquivo usar
        if user_agents_file is None:
            user_agents_file = get_default_user_agents_file()
        
        try:
            # Tentar carregar do arquivo
            loaded_agents = load_user_agents_from_file(user_agents_file)
            
            if loaded_agents:
                # Sucesso! Usar os user agents do arquivo
                self.CUSTOM_USER_AGENTS = loaded_agents
                logger.info(
                    f"📄 Loaded {len(loaded_agents)} user agents from {user_agents_file.name}"
                )
            else:
                # Arquivo vazio, usar fallback
                logger.warning(
                    f"⚠️ File {user_agents_file.name} is empty, using hardcoded fallback "
                    f"({len(self.CUSTOM_USER_AGENTS)} user agents)"
                )
                
        except FileNotFoundError:
            # Arquivo não existe, usar fallback
            logger.info(
                f"ℹ️ File {user_agents_file.name} not found, using hardcoded fallback "
                f"({len(self.CUSTOM_USER_AGENTS)} user agents)"
            )
        except Exception as e:
            # Outro erro, usar fallback
            logger.warning(
                f"⚠️ Error loading user agents from {user_agents_file.name}: {e}, "
                f"using hardcoded fallback ({len(self.CUSTOM_USER_AGENTS)} user agents)"
            )
    
    def __init__(self, enable_rotation: bool = True, use_fake_useragent: bool = True, user_agents_file: Optional[Path] = None):
        """
        Inicializa rotacionador.
        
        Args:
            enable_rotation: Se False, usa sempre o primeiro UA
            use_fake_useragent: Se True, tenta usar fake-useragent lib
            user_agents_file: Path to custom user agents file (defaults to user-agents.txt in project root)
        """
        self.enable_rotation = enable_rotation
        self.use_fake_useragent = use_fake_useragent and HAS_FAKE_USERAGENT
        
        # Tentar carregar user agents do arquivo
        self._load_user_agents(user_agents_file)
        
        self.fake_ua = None
        if self.use_fake_useragent:
            try:
                self.fake_ua = UserAgent(
                    browsers=['chrome', 'firefox', 'safari', 'edge'],
                    os=['windows', 'macos', 'linux'],
                    min_percentage=1.0
                )
                logger.info("✅ fake-useragent initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize fake-useragent: {e}")
                self.use_fake_useragent = False
        
        self.current_index = 0
        self.rotation_count = 0
        
        logger.info(
            f"UserAgentRotator initialized: "
            f"rotation={enable_rotation}, "
            f"fake_ua={self.use_fake_useragent}, "
            f"custom_pool={len(self.CUSTOM_USER_AGENTS)}"
        )
    
    def get_random(self) -> str:
        """
        Retorna User-Agent aleatório.
        
        Returns:
            str: User-Agent
        """
        if not self.enable_rotation:
            return self.CUSTOM_USER_AGENTS[0]
        
        # 70% chance: usar fake-useragent (se disponível)
        if self.use_fake_useragent and random.random() < 0.7:
            try:
                ua = self.fake_ua.random
                self.rotation_count += 1
                logger.debug(f"🔄 Rotated UA (fake_ua #{self.rotation_count}): {ua[:80]}...")
                return ua
            except Exception as e:
                logger.warning(f"fake-useragent error: {e}, falling back to custom")
        
        # 30% chance ou fallback: usar lista customizada
        ua = random.choice(self.CUSTOM_USER_AGENTS)
        self.rotation_count += 1
        logger.debug(f"🔄 Rotated UA (custom #{self.rotation_count}): {ua[:80]}...")
        return ua
    
    def get_next(self) -> str:
        """
        Retorna próximo User-Agent (rotação sequencial).
        
        Returns:
            str: User-Agent
        """
        if not self.enable_rotation:
            return self.CUSTOM_USER_AGENTS[0]
        
        ua = self.CUSTOM_USER_AGENTS[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.CUSTOM_USER_AGENTS)
        self.rotation_count += 1
        
        logger.debug(f"🔄 Rotated UA (sequential #{self.rotation_count}): {ua[:80]}...")
        return ua
    
    def get_mobile(self) -> str:
        """
        Retorna User-Agent mobile.
        
        Returns:
            str: User-Agent mobile
        """
        mobile_uas = [ua for ua in self.CUSTOM_USER_AGENTS if 'Mobile' in ua or 'iPhone' in ua or 'Android' in ua]
        return random.choice(mobile_uas) if mobile_uas else self.get_random()
    
    def get_desktop(self) -> str:
        """
        Retorna User-Agent desktop.
        
        Returns:
            str: User-Agent desktop
        """
        desktop_uas = [ua for ua in self.CUSTOM_USER_AGENTS if 'Mobile' not in ua and 'iPhone' not in ua]
        return random.choice(desktop_uas) if desktop_uas else self.get_random()
    
    def get_stats(self) -> dict:
        """
        Retorna estatísticas de rotação.
        
        Returns:
            dict: Estatísticas
        """
        return {
            "rotation_enabled": self.enable_rotation,
            "fake_ua_enabled": self.use_fake_useragent,
            "custom_pool_size": len(self.CUSTOM_USER_AGENTS),
            "rotation_count": self.rotation_count,
            "current_index": self.current_index
        }


# Instância global (singleton)
_ua_rotator: Optional[UserAgentRotator] = None


def get_ua_rotator(enable_rotation: bool = True, use_fake_useragent: bool = True, user_agents_file: Optional[Path] = None) -> UserAgentRotator:
    """
    Retorna instância singleton do rotacionador.
    
    Args:
        enable_rotation: Se False, usa sempre o primeiro UA
        use_fake_useragent: Se True, tenta usar fake-useragent lib
        user_agents_file: Path to custom user agents file (defaults to user-agents.txt)
        
    Returns:
        UserAgentRotator
    """
    global _ua_rotator
    if _ua_rotator is None:
        _ua_rotator = UserAgentRotator(enable_rotation, use_fake_useragent, user_agents_file)
    return _ua_rotator
