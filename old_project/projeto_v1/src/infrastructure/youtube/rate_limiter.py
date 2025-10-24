"""
YouTube Rate Limiter - v3.0

Controla taxa de requisições para evitar bloqueio/banimento.
Implementa sliding window + cooldown após erros.
"""
import time
import asyncio
import random
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger


@dataclass
class RateLimitWindow:
    """
    Janela de rate limiting.
    
    Attributes:
        window_seconds: Duração da janela em segundos
        max_requests: Máximo de requisições na janela
        requests: Lista de timestamps de requisições
    """
    window_seconds: int
    max_requests: int
    requests: List[float] = field(default_factory=list)
    
    def cleanup_old_requests(self):
        """Remove requisições fora da janela."""
        current_time = time.time()
        cutoff = current_time - self.window_seconds
        self.requests = [t for t in self.requests if t > cutoff]
    
    def can_make_request(self) -> bool:
        """Verifica se pode fazer requisição."""
        self.cleanup_old_requests()
        return len(self.requests) < self.max_requests
    
    def add_request(self):
        """Registra nova requisição."""
        self.requests.append(time.time())
    
    def get_wait_time(self) -> float:
        """
        Calcula tempo de espera até próxima requisição.
        
        Returns:
            float: Segundos a esperar (0 se pode fazer agora)
        """
        self.cleanup_old_requests()
        
        if len(self.requests) < self.max_requests:
            return 0.0
        
        # Tempo até a requisição mais antiga sair da janela
        oldest = min(self.requests)
        wait_until = oldest + self.window_seconds
        wait_time = wait_until - time.time()
        
        return max(0.0, wait_time)


class YouTubeRateLimiter:
    """
    Rate Limiter para requisições ao YouTube.
    
    Features:
    - Sliding window para controle de taxa
    - Cooldown aumentado após erros
    - Random jitter para parecer mais humano
    - Estatísticas de uso
    """
    
    def __init__(
        self,
        requests_per_minute: int = 10,
        requests_per_hour: int = 200,
        cooldown_on_error: int = 60,
        enable_jitter: bool = True,
        jitter_range: tuple = (1, 5)
    ):
        """
        Inicializa rate limiter.
        
        Args:
            requests_per_minute: Máximo de requisições por minuto
            requests_per_hour: Máximo de requisições por hora
            cooldown_on_error: Segundos de cooldown após erro
            enable_jitter: Se True, adiciona delay aleatório
            jitter_range: Tupla (min, max) de segundos para jitter
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.cooldown_on_error = cooldown_on_error
        self.enable_jitter = enable_jitter
        self.jitter_range = jitter_range
        
        # Janelas de rate limiting
        self.minute_window = RateLimitWindow(60, requests_per_minute)
        self.hour_window = RateLimitWindow(3600, requests_per_hour)
        
        # Cooldown state
        self.in_cooldown = False
        self.cooldown_until: Optional[float] = None
        self.error_count = 0
        self.consecutive_errors = 0
        
        # Estatísticas
        self.total_requests = 0
        self.total_wait_time = 0.0
        self.total_jitter_time = 0.0
        self.cooldown_count = 0
        
        logger.info(
            f"YouTubeRateLimiter initialized: "
            f"{requests_per_minute}/min, {requests_per_hour}/hour, "
            f"cooldown={cooldown_on_error}s, jitter={enable_jitter}"
        )
    
    async def wait_if_needed(self):
        """
        Aguarda se necessário para respeitar rate limit.
        
        Implementa:
        1. Cooldown após erros
        2. Rate limiting por minuto/hora
        3. Random jitter (parecer mais humano)
        """
        # 1. Verificar cooldown
        if self.in_cooldown:
            wait_time = max(0.0, self.cooldown_until - time.time())
            if wait_time > 0:
                logger.warning(
                    f"⏸️  In cooldown mode: waiting {wait_time:.1f}s "
                    f"(errors={self.error_count}, consecutive={self.consecutive_errors})"
                )
                await asyncio.sleep(wait_time)
                self.total_wait_time += wait_time
            
            # Sair do cooldown
            self.in_cooldown = False
            self.cooldown_until = None
            self.consecutive_errors = 0
            logger.info("✅ Cooldown finished, resuming normal operation")
        
        # 2. Rate limiting por janela
        minute_wait = self.minute_window.get_wait_time()
        hour_wait = self.hour_window.get_wait_time()
        max_wait = max(minute_wait, hour_wait)
        
        if max_wait > 0:
            logger.info(
                f"⏱️  Rate limit reached: waiting {max_wait:.1f}s "
                f"(minute={len(self.minute_window.requests)}/{self.requests_per_minute}, "
                f"hour={len(self.hour_window.requests)}/{self.requests_per_hour})"
            )
            await asyncio.sleep(max_wait)
            self.total_wait_time += max_wait
        
        # 3. Jitter (delay aleatório para parecer humano)
        if self.enable_jitter:
            jitter = random.uniform(*self.jitter_range)
            logger.debug(f"💤 Adding jitter: {jitter:.2f}s")
            await asyncio.sleep(jitter)
            self.total_jitter_time += jitter
        
        # Registrar requisição
        self.minute_window.add_request()
        self.hour_window.add_request()
        self.total_requests += 1
    
    def report_error(self):
        """
        Reporta erro de download.
        
        Aumenta cooldown exponencialmente com erros consecutivos.
        """
        self.error_count += 1
        self.consecutive_errors += 1
        
        # Cooldown exponencial: 60s, 120s, 240s, 480s, ...
        cooldown_multiplier = min(2 ** (self.consecutive_errors - 1), 8)
        cooldown_seconds = self.cooldown_on_error * cooldown_multiplier
        
        self.in_cooldown = True
        self.cooldown_until = time.time() + cooldown_seconds
        self.cooldown_count += 1
        
        logger.error(
            f"🔥 Error reported: entering cooldown for {cooldown_seconds}s "
            f"(consecutive={self.consecutive_errors}, total={self.error_count})"
        )
    
    def report_success(self):
        """Reporta sucesso de download (reseta erros consecutivos)."""
        if self.consecutive_errors > 0:
            logger.info(
                f"✅ Success after {self.consecutive_errors} consecutive errors - "
                "resetting cooldown multiplier"
            )
        self.consecutive_errors = 0
    
    def get_stats(self) -> Dict:
        """
        Retorna estatísticas do rate limiter.
        
        Returns:
            dict: Estatísticas
        """
        current_minute = len(self.minute_window.requests)
        current_hour = len(self.hour_window.requests)
        
        avg_wait = self.total_wait_time / self.total_requests if self.total_requests > 0 else 0
        avg_jitter = self.total_jitter_time / self.total_requests if self.total_requests > 0 else 0
        
        return {
            "total_requests": self.total_requests,
            "current_minute": f"{current_minute}/{self.requests_per_minute}",
            "current_hour": f"{current_hour}/{self.requests_per_hour}",
            "total_errors": self.error_count,
            "consecutive_errors": self.consecutive_errors,
            "in_cooldown": self.in_cooldown,
            "cooldown_count": self.cooldown_count,
            "total_wait_time_seconds": round(self.total_wait_time, 2),
            "total_jitter_time_seconds": round(self.total_jitter_time, 2),
            "avg_wait_per_request_seconds": round(avg_wait, 2),
            "avg_jitter_per_request_seconds": round(avg_jitter, 2),
        }


# Instância global (singleton)
_rate_limiter: Optional[YouTubeRateLimiter] = None


def get_rate_limiter(
    requests_per_minute: int = 10,
    requests_per_hour: int = 200,
    cooldown_on_error: int = 60
) -> YouTubeRateLimiter:
    """
    Retorna instância singleton do rate limiter.
    
    Args:
        requests_per_minute: Máximo de requisições por minuto
        requests_per_hour: Máximo de requisições por hora
        cooldown_on_error: Segundos de cooldown após erro
        
    Returns:
        YouTubeRateLimiter
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = YouTubeRateLimiter(
            requests_per_minute,
            requests_per_hour,
            cooldown_on_error
        )
    return _rate_limiter
