"""
Middleware de métricas Prometheus.

v2.2: Instrumentação automática de endpoints com métricas customizadas.
"""
from time import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from loguru import logger

from src.infrastructure.monitoring import MetricsCollector


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware para coletar métricas automaticamente de todas as requisições.
    
    v2.2: Coleta métricas de duração e erros para todos os endpoints.
    """
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Intercepta requisições e coleta métricas.
        
        Args:
            request: Requisição HTTP
            call_next: Próximo handler na cadeia
            
        Returns:
            Response: Resposta HTTP
        """
        # Extrai informações da requisição
        endpoint = request.url.path
        method = request.method
        start_time = time()
        
        # Marca requisição como em andamento
        status_code = 500
        error_type = None
        
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            return response
            
        except Exception as e:
            error_type = type(e).__name__
            logger.error(f"Error in middleware: {error_type}")
            raise
            
        finally:
            # Calcula duração
            duration = time() - start_time
            
            # Registra erro se houve
            if error_type or status_code >= 400:
                MetricsCollector.record_api_error(
                    endpoint=endpoint,
                    error_type=error_type or f"HTTP_{status_code}",
                    status_code=status_code
                )
            
            # Log de debug
            logger.debug(
                f"📊 Request completed: {method} {endpoint} - {status_code} ({duration:.3f}s)"
            )
