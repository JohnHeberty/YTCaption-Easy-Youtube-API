"""
Health Checker para microserviços.

Verifica saúde de todos os serviços e reporta status consolidado.
"""
from typing import Dict

from common.log_utils import get_logger
from domain.interfaces import HealthCheckable

logger = get_logger(__name__)


class HealthChecker:
    """
    Verificador de saúde de microserviços.

    Responsabilidade única: verificar saúde de serviços externos.
    """

    def __init__(self, clients: Dict[str, HealthCheckable]) -> None:
        """
        Inicializa HealthChecker.

        Args:
            clients: Dict de nome -> cliente que implementa HealthCheckable
        """
        self.clients = clients

    async def check_all(self) -> Dict[str, str]:
        """
        Verifica saúde de todos os serviços.

        Returns:
            Dict com nome do serviço -> status
        """
        results: Dict[str, str] = {}
        for name, client in self.clients.items():
            try:
                health = await client.check_health()
                status = health.get("status", "unknown")
                results[name] = status
                if status == "healthy":
                    logger.debug(f"Health check OK for {name}")
                else:
                    logger.warning(f"Health check returned '{status}' for {name}")
            except Exception as e:
                results[name] = f"error: {e}"
                logger.error(f"Health check failed for {name}: {e}")
        return results

    async def check_service(self, name: str) -> str:
        """
        Verifica saúde de um serviço específico.

        Args:
            name: Nome do serviço

        Returns:
            Status do serviço
        """
        client = self.clients.get(name)
        if not client:
            logger.error(f"Service {name} not found in health checker")
            return "not_found"

        try:
            health = await client.check_health()
            return health.get("status", "unknown")
        except Exception as e:
            logger.error(f"Health check failed for {name}: {e}")
            return f"error: {e}"
