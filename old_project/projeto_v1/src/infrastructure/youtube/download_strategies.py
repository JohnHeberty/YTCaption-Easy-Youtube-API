"""
YouTube Download Strategies - v3.0

Múltiplas estratégias de download com fallback automático.
Evita bloqueios do YouTube usando diferentes clients e configurações.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class DownloadStrategy:
    """
    Estratégia de download do YouTube.
    
    Attributes:
        name: Nome da estratégia
        player_client: Lista de clients do YouTube a tentar
        user_agent: User agent customizado (opcional)
        extra_opts: Opções extras para yt-dlp
        priority: Prioridade (menor = tenta primeiro)
    """
    name: str
    player_client: List[str]
    user_agent: Optional[str] = None
    extra_opts: Optional[Dict] = None
    priority: int = 0
    
    def to_ydl_opts(self, base_opts: Dict) -> Dict:
        """
        Converte estratégia em opções do yt-dlp.
        
        Args:
            base_opts: Opções base do yt-dlp
            
        Returns:
            Dict com opções mescladas
        """
        opts = base_opts.copy()
        
        # Configurar player_client
        if 'extractor_args' not in opts:
            opts['extractor_args'] = {}
        if 'youtube' not in opts['extractor_args']:
            opts['extractor_args']['youtube'] = {}
            
        opts['extractor_args']['youtube']['player_client'] = self.player_client
        
        # User agent customizado
        if self.user_agent:
            if 'http_headers' not in opts:
                opts['http_headers'] = {}
            opts['http_headers']['User-Agent'] = self.user_agent
        
        # Mesclar opções extras
        if self.extra_opts:
            opts.update(self.extra_opts)
        
        return opts


class DownloadStrategyManager:
    """
    Gerenciador de estratégias de download com fallback.
    
    Tenta múltiplas estratégias em ordem de prioridade até uma funcionar.
    """
    
    # Estratégias disponíveis (ordenadas por prioridade)
    STRATEGIES = [
        # Estratégia 1: Android client (mais confiável)
        DownloadStrategy(
            name="android_client",
            player_client=["android"],
            user_agent="com.google.android.youtube/19.09.37 (Linux; U; Android 13) gzip",
            priority=1
        ),
        
        # Estratégia 2: Android Music client
        DownloadStrategy(
            name="android_music",
            player_client=["android_music"],
            user_agent="com.google.android.apps.youtube.music/6.42.52 (Linux; U; Android 13) gzip",
            priority=2
        ),
        
        # Estratégia 3: iOS client
        DownloadStrategy(
            name="ios_client",
            player_client=["ios"],
            user_agent="com.google.ios.youtube/19.09.3 (iPhone16,2; U; CPU iOS 17_4 like Mac OS X;)",
            priority=3
        ),
        
        # Estratégia 4: Web client com embed
        DownloadStrategy(
            name="web_embed",
            player_client=["web"],
            extra_opts={
                'extractor_args': {
                    'youtube': {
                        'player_client': ['web'],
                        'player_skip': ['webpage'],
                    }
                }
            },
            priority=4
        ),
        
        # Estratégia 5: TV Embedded client
        DownloadStrategy(
            name="tv_embedded",
            player_client=["tv_embedded"],
            priority=5
        ),
        
        # Estratégia 6: MWEB (mobile web)
        DownloadStrategy(
            name="mweb",
            player_client=["mweb"],
            user_agent="Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            priority=6
        ),
        
        # Estratégia 7: Sem player_client (padrão yt-dlp)
        DownloadStrategy(
            name="default",
            player_client=[],
            extra_opts={
                'extractor_args': {
                    'youtube': {
                        'player_skip': ['configs'],
                    }
                }
            },
            priority=7
        ),
    ]
    
    def __init__(self, enable_multi_strategy: bool = True):
        """
        Inicializa gerenciador de estratégias.
        
        Args:
            enable_multi_strategy: Se False, usa apenas primeira estratégia
        """
        self.enable_multi_strategy = enable_multi_strategy
        self.strategies = sorted(self.STRATEGIES, key=lambda s: s.priority)
        
        if not enable_multi_strategy:
            self.strategies = [self.strategies[0]]
            logger.info(f"Multi-strategy disabled, using only: {self.strategies[0].name}")
        else:
            logger.info(f"Multi-strategy enabled with {len(self.strategies)} strategies")
    
    def get_strategies(self) -> List[DownloadStrategy]:
        """Retorna lista de estratégias em ordem de prioridade."""
        return self.strategies
    
    def get_strategy_by_name(self, name: str) -> Optional[DownloadStrategy]:
        """
        Busca estratégia por nome.
        
        Args:
            name: Nome da estratégia
            
        Returns:
            DownloadStrategy ou None se não encontrada
        """
        for strategy in self.strategies:
            if strategy.name == name:
                return strategy
        return None
    
    def log_strategy_attempt(self, strategy: DownloadStrategy, attempt: int, total: int):
        """
        Loga tentativa de download com estratégia.
        
        Args:
            strategy: Estratégia sendo tentada
            attempt: Número da tentativa atual
            total: Total de estratégias disponíveis
        """
        logger.info(
            f"🎯 Download strategy [{attempt}/{total}]: {strategy.name} "
            f"(player_client={strategy.player_client})"
        )
    
    def log_strategy_success(self, strategy: DownloadStrategy):
        """
        Loga sucesso de estratégia.
        
        Args:
            strategy: Estratégia que funcionou
        """
        logger.success(f"✅ Strategy successful: {strategy.name}")
    
    def log_strategy_failure(self, strategy: DownloadStrategy, error: str):
        """
        Loga falha de estratégia.
        
        Args:
            strategy: Estratégia que falhou
            error: Mensagem de erro
        """
        logger.warning(f"❌ Strategy failed: {strategy.name} - {error}")
    
    def log_all_strategies_failed(self):
        """Loga quando todas as estratégias falharam."""
        logger.error(
            f"🔥 All {len(self.strategies)} download strategies failed! "
            "YouTube may have blocked this IP or video is restricted."
        )


# Instância global (singleton)
_strategy_manager: Optional[DownloadStrategyManager] = None


def get_strategy_manager(enable_multi_strategy: bool = True) -> DownloadStrategyManager:
    """
    Retorna instância singleton do gerenciador de estratégias.
    
    Args:
        enable_multi_strategy: Se False, usa apenas primeira estratégia
        
    Returns:
        DownloadStrategyManager
    """
    global _strategy_manager
    if _strategy_manager is None:
        _strategy_manager = DownloadStrategyManager(enable_multi_strategy)
    return _strategy_manager
