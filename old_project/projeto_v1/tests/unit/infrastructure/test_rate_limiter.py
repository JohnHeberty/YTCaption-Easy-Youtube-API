"""
Testes unitários para YouTubeRateLimiter.
"""
import pytest
import asyncio
import time
from src.infrastructure.youtube.rate_limiter import YouTubeRateLimiter


class TestYouTubeRateLimiter:
    """Testes para rate limiter do YouTube."""
    
    def test_rate_limiter_initialization(self):
        """Deve inicializar com configurações corretas."""
        limiter = YouTubeRateLimiter(
            requests_per_minute=10,
            requests_per_hour=200,
            cooldown_on_error=60
        )
        
        assert limiter.requests_per_minute == 10
        assert limiter.requests_per_hour == 200
        assert limiter.cooldown_on_error == 60
        assert limiter.error_count == 0
        assert limiter.consecutive_errors == 0
        assert not limiter.in_cooldown
    
    @pytest.mark.asyncio
    async def test_wait_if_needed_first_request(self):
        """Primeira requisição não deve esperar."""
        limiter = YouTubeRateLimiter(requests_per_minute=10)
        
        start = time.time()
        await limiter.wait_if_needed()
        elapsed = time.time() - start
        
        # Primeira requisição deve ser instantânea (apenas jitter < 1s)
        assert elapsed < 1.5
    
    @pytest.mark.asyncio
    async def test_rate_limiting_enforced(self):
        """Deve enforçar rate limit."""
        # Rate limit muito baixo para forçar espera
        limiter = YouTubeRateLimiter(
            requests_per_minute=2,  # Apenas 2 por minuto
            enable_jitter=False  # Desabilitar jitter para teste
        )
        
        # Fazer 2 requisições rapidamente
        await limiter.wait_if_needed()
        await limiter.wait_if_needed()
        
        # Terceira requisição deve esperar
        start = time.time()
        await limiter.wait_if_needed()
        elapsed = time.time() - start
        
        # Deve ter esperado alguns segundos
        assert elapsed > 0.1  # Pelo menos algum delay
    
    def test_report_error_increases_count(self):
        """Deve incrementar contador de erros."""
        limiter = YouTubeRateLimiter()
        
        initial_errors = limiter.error_count
        limiter.report_error()
        
        assert limiter.error_count == initial_errors + 1
        assert limiter.consecutive_errors == 1
        assert limiter.in_cooldown
    
    def test_report_error_exponential_cooldown(self):
        """Cooldown deve crescer exponencialmente."""
        limiter = YouTubeRateLimiter(cooldown_on_error=10)
        
        # Primeiro erro: 10s cooldown
        limiter.report_error()
        first_cooldown = limiter.cooldown_until - time.time()
        
        # Segundo erro: 20s cooldown
        limiter.report_error()
        second_cooldown = limiter.cooldown_until - time.time()
        
        # Segundo cooldown deve ser maior
        assert second_cooldown > first_cooldown
    
    def test_report_success_resets_consecutive_errors(self):
        """Sucesso deve resetar erros consecutivos."""
        limiter = YouTubeRateLimiter()
        
        # Simular alguns erros
        limiter.report_error()
        limiter.report_error()
        assert limiter.consecutive_errors == 2
        
        # Sucesso reseta
        limiter.report_success()
        assert limiter.consecutive_errors == 0
    
    def test_get_stats(self):
        """Deve retornar estatísticas corretas."""
        limiter = YouTubeRateLimiter(requests_per_minute=10)
        
        stats = limiter.get_stats()
        
        assert 'total_requests' in stats
        assert 'current_minute' in stats
        assert 'current_hour' in stats
        assert 'total_errors' in stats
        assert 'in_cooldown' in stats
    
    @pytest.mark.asyncio
    async def test_cooldown_prevents_requests(self):
        """Cooldown deve fazer wait antes de permitir requisição."""
        limiter = YouTubeRateLimiter(cooldown_on_error=1)  # 1s cooldown
        
        # Causar erro
        limiter.report_error()
        assert limiter.in_cooldown
        
        # Próxima requisição deve esperar
        start = time.time()
        await limiter.wait_if_needed()
        elapsed = time.time() - start
        
        # Deve ter esperado pelo menos quase todo o cooldown
        assert elapsed >= 0.5  # Pelo menos metade do cooldown
        assert not limiter.in_cooldown  # Cooldown deve ter acabado
