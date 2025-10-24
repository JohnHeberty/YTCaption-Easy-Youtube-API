"""
Middleware para logging de requisições.
Registra todas as requisições e respostas da API.
"""
import time
from typing import Callable
from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware para logging de requisições HTTP."""
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Processa requisição e registra logs.
        
        Args:
            request: Requisição HTTP
            call_next: Próximo handler
            
        Returns:
            Response: Resposta HTTP
        """
        # Registrar início da requisição
        start_time = time.time()
        
        # Informações da requisição
        client_host = request.client.host if request.client else "unknown"
        
        logger.info(
            f"Request started: {request.method} {request.url.path} "
            f"from {client_host}"
        )
        
        # Processar requisição
        try:
            response = await call_next(request)
            
            # Calcular tempo de processamento
            process_time = time.time() - start_time
            
            # Registrar conclusão
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"status={response.status_code} time={process_time:.3f}s"
            )
            
            # Adicionar header com tempo de processamento
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            # Registrar erro
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"error={str(e)} time={process_time:.3f}s"
            )
            raise
