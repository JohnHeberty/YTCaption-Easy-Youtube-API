"""
Testes unitários para HealthChecker.
"""
from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest

from services.health_checker import HealthChecker


class TestHealthChecker:
    """Testes para HealthChecker."""

    @pytest.mark.asyncio
    async def test_check_all_returns_statuses(self):
        """Deve retornar status de todos os serviços."""
        mock_client1 = AsyncMock()
        mock_client1.check_health.return_value = {"status": "healthy"}

        mock_client2 = AsyncMock()
        mock_client2.check_health.return_value = {"status": "healthy"}

        clients = {
            "service1": mock_client1,
            "service2": mock_client2,
        }

        checker = HealthChecker(clients)
        results = await checker.check_all()

        assert results["service1"] == "healthy"
        assert results["service2"] == "healthy"

    @pytest.mark.asyncio
    async def test_check_all_handles_errors(self):
        """Deve lidar com erros de health check."""
        mock_healthy = AsyncMock()
        mock_healthy.check_health.return_value = {"status": "healthy"}

        mock_failing = AsyncMock()
        mock_failing.check_health.side_effect = Exception("Connection failed")

        clients = {
            "healthy": mock_healthy,
            "failing": mock_failing,
        }

        checker = HealthChecker(clients)
        results = await checker.check_all()

        assert results["healthy"] == "healthy"
        assert "error" in results["failing"]
        assert "Connection failed" in results["failing"]

    @pytest.mark.asyncio
    async def test_check_all_handles_unknown_status(self):
        """Deve lidar com status desconhecido."""
        mock_client = AsyncMock()
        mock_client.check_health.return_value = {"version": "1.0.0"}  # Sem status

        clients = {"service": mock_client}
        checker = HealthChecker(clients)
        results = await checker.check_all()

        assert results["service"] == "unknown"

    @pytest.mark.asyncio
    async def test_check_service_specific(self):
        """Deve verificar serviço específico."""
        mock_client = AsyncMock()
        mock_client.check_health.return_value = {"status": "healthy"}

        clients = {"test-service": mock_client}
        checker = HealthChecker(clients)

        result = await checker.check_service("test-service")
        assert result == "healthy"

    @pytest.mark.asyncio
    async def test_check_service_not_found(self):
        """Deve retornar not_found para serviço inexistente."""
        checker = HealthChecker({})
        result = await checker.check_service("nonexistent")
        assert result == "not_found"

    @pytest.mark.asyncio
    async def test_empty_clients(self):
        """Deve funcionar com lista vazia."""
        checker = HealthChecker({})
        results = await checker.check_all()
        assert results == {}

    @pytest.mark.asyncio
    async def test_multiple_services_mixed_status(self):
        """Deve lidar com múltiplos serviços em estados diferentes."""
        mock_healthy = AsyncMock()
        mock_healthy.check_health.return_value = {"status": "healthy"}

        mock_unhealthy = AsyncMock()
        mock_unhealthy.check_health.return_value = {"status": "degraded"}

        mock_failing = AsyncMock()
        mock_failing.check_health.side_effect = Exception("Timeout")

        clients = {
            "healthy-service": mock_healthy,
            "degraded-service": mock_unhealthy,
            "failing-service": mock_failing,
        }

        checker = HealthChecker(clients)
        results = await checker.check_all()

        assert results["healthy-service"] == "healthy"
        assert results["degraded-service"] == "degraded"
        assert "error" in results["failing-service"]
