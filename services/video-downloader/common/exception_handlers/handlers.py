"""
Standard exception handlers for FastAPI applications
"""
import logging
from typing import Callable
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class BaseServiceException(Exception):
    """Exceção base para todos os serviços"""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "INTERNAL_ERROR",
        details: dict = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationException(BaseServiceException):
    """Exceção de validação"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="VALIDATION_ERROR",
            details=details
        )


class ResourceNotFoundException(BaseServiceException):
    """Exceção quando recurso não é encontrado"""
    
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            message=f"{resource_type} not found: {resource_id}",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="RESOURCE_NOT_FOUND",
            details={
                "resource_type": resource_type,
                "resource_id": resource_id
            }
        )


class ProcessingException(BaseServiceException):
    """Exceção durante processamento"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="PROCESSING_ERROR",
            details=details
        )


class ServiceUnavailableException(BaseServiceException):
    """Exceção quando serviço está indisponível"""
    
    def __init__(self, service_name: str, reason: str = None):
        message = f"Service unavailable: {service_name}"
        if reason:
            message += f" - {reason}"
        
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="SERVICE_UNAVAILABLE",
            details={
                "service_name": service_name,
                "reason": reason
            }
        )


class RateLimitException(BaseServiceException):
    """Exceção quando rate limit é excedido"""
    
    def __init__(self, limit: int, window: str):
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window}",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="RATE_LIMIT_EXCEEDED",
            details={
                "limit": limit,
                "window": window
            }
        )


def create_exception_handler(
    exception_class: type,
    default_status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    log_traceback: bool = True
) -> Callable:
    """
    Factory para criar exception handlers.
    
    Args:
        exception_class: Classe da exceção
        default_status_code: Status code padrão
        log_traceback: Se deve logar traceback completo
    
    Returns:
        Handler function
    """
    
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        """Handler da exceção"""
        
        # Extrai informações da exceção
        if isinstance(exc, BaseServiceException):
            status_code = exc.status_code
            error_code = exc.error_code
            message = exc.message
            details = exc.details
        else:
            status_code = default_status_code
            error_code = "INTERNAL_ERROR"
            message = str(exc)
            details = {}
        
        # Log
        log_data = {
            'error_code': error_code,
            'status_code': status_code,
            'message': message,
            'path': request.url.path,
            'method': request.method
        }
        
        if log_traceback:
            logger.error(f"Exception occurred: {error_code}", exc_info=True, extra=log_data)
        else:
            logger.error(f"Exception occurred: {error_code}", extra=log_data)
        
        # Resposta
        response_data = {
            'error': error_code,
            'message': message
        }
        
        if details:
            response_data['details'] = details
        
        return JSONResponse(
            status_code=status_code,
            content=response_data
        )
    
    return handler


def setup_exception_handlers(app: FastAPI, debug: bool = False):
    """
    Configura exception handlers padrão para a aplicação.
    
    Args:
        app: Instância FastAPI
        debug: Se True, inclui detalhes completos de erros
    
    Examples:
        >>> app = FastAPI()
        >>> setup_exception_handlers(app, debug=False)
    """
    
    # Handler para BaseServiceException e subclasses
    @app.exception_handler(BaseServiceException)
    async def service_exception_handler(request: Request, exc: BaseServiceException):
        logger.error(
            f"Service exception: {exc.error_code}",
            exc_info=True,
            extra={
                'error_code': exc.error_code,
                'status_code': exc.status_code,
                'path': request.url.path,
                'method': request.method
            }
        )
        
        response_data = {
            'error': exc.error_code,
            'message': exc.message
        }
        
        if exc.details:
            response_data['details'] = exc.details
        
        return JSONResponse(
            status_code=exc.status_code,
            content=response_data
        )
    
    # Handler para validation errors do Pydantic
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(
            "Validation error",
            extra={
                'path': request.url.path,
                'method': request.method,
                'errors': exc.errors()
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                'error': 'VALIDATION_ERROR',
                'message': 'Request validation failed',
                'details': exc.errors()
            }
        )
    
    # Handler para HTTP exceptions do Starlette
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.warning(
            f"HTTP exception: {exc.status_code}",
            extra={
                'status_code': exc.status_code,
                'path': request.url.path,
                'method': request.method
            }
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                'error': 'HTTP_ERROR',
                'message': exc.detail
            }
        )
    
    # Handler global para exceções não tratadas
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.critical(
            "Unhandled exception",
            exc_info=True,
            extra={
                'path': request.url.path,
                'method': request.method,
                'exception_type': type(exc).__name__
            }
        )
        
        response_data = {
            'error': 'INTERNAL_ERROR',
            'message': 'An unexpected error occurred'
        }
        
        # Em debug mode, inclui detalhes
        if debug:
            response_data['details'] = {
                'exception_type': type(exc).__name__,
                'exception_message': str(exc)
            }
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response_data
        )
    
    logger.info("Exception handlers configured")
