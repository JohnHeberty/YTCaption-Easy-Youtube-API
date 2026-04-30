"""
Testes de integração entre serviços.
"""
import pytest


@pytest.mark.integration
class TestServiceIntegration:
    """Testes de integração com serviços reais (requerem serviços rodando)."""

    @pytest.mark.asyncio
    async def test_config_loading(self):
        """Deve carregar configurações."""
        from core.config import get_settings

        settings = get_settings()
        assert settings.video_downloader_url.startswith("http")
        assert settings.audio_normalization_url.startswith("http")
        assert settings.audio_transcriber_url.startswith("http")

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Deve criar circuit breaker funcional."""
        from infrastructure.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        assert cb.state.value == "closed"

    @pytest.mark.asyncio
    async def test_job_id_validator(self):
        """Deve validar job IDs corretamente."""
        from core.validators import JobIdValidator

        assert JobIdValidator.validate("valid-job-123") is True
        assert JobIdValidator.validate("../etc/passwd") is False


@pytest.mark.skip(reason="Requires running microservices")
class TestLiveServices:
    """Testes que requerem serviços rodando."""

    @pytest.mark.asyncio
    async def test_health_endpoints(self):
        """Deve verificar health de serviços reais."""
        import httpx
        from core.config import get_settings

        settings = get_settings()
        services = [
            ("video-downloader", settings.video_downloader_url),
            ("audio-normalization", settings.audio_normalization_url),
            ("audio-transcriber", settings.audio_transcriber_url),
        ]

        async with httpx.AsyncClient() as client:
            for name, url in services:
                try:
                    response = await client.get(f"{url}/health", timeout=5.0)
                    assert response.status_code == 200
                except Exception:
                    pytest.skip(f"Service {name} not available")
