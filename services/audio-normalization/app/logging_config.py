"""
Sistema de logging estruturado com correlation ID e métricas
"""
import json
import uuid
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar
from functools import wraps
from pathlib import Path

# ContextVar para correlation ID thread-safe
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class CorrelationIdFilter(logging.Filter):
    """Filtro para adicionar correlation ID aos logs"""
    
    def filter(self, record):
        record.correlation_id = correlation_id.get() or "unknown"
        return True


class StructuredFormatter(logging.Formatter):
    """Formatter para logs estruturados em JSON"""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, 'correlation_id', 'unknown'),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Adiciona campos extras se existirem
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Adiciona exception info se existir
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        return json.dumps(log_entry, ensure_ascii=False)


class PerformanceLogger:
    """Logger especializado para métricas de performance"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def log_request_metrics(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        file_size: int = None,
        processing_time: float = None
    ):
        """Log de métricas de requisição"""
        metrics = {
            "type": "request_metrics",
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration_ms": duration_ms,
        }
        
        if file_size:
            metrics["file_size_bytes"] = file_size
        
        if processing_time:
            metrics["processing_time_ms"] = processing_time
        
        self.logger.info("Request completed", extra={"extra_fields": metrics})
    
    def log_processing_metrics(
        self,
        job_id: str,
        operation: str,
        duration_ms: float,
        input_size: int = None,
        output_size: int = None,
        success: bool = True
    ):
        """Log de métricas de processamento"""
        metrics = {
            "type": "processing_metrics",
            "job_id": job_id,
            "operation": operation,
            "duration_ms": duration_ms,
            "success": success,
        }
        
        if input_size:
            metrics["input_size_bytes"] = input_size
        
        if output_size:
            metrics["output_size_bytes"] = output_size
            if input_size:
                metrics["compression_ratio"] = output_size / input_size
        
        level = logging.INFO if success else logging.WARNING
        self.logger.log(level, f"Processing {operation} completed", extra={"extra_fields": metrics})
    
    def log_resource_metrics(
        self,
        cpu_percent: float = None,
        memory_mb: float = None,
        disk_usage_mb: float = None,
        active_jobs: int = None
    ):
        """Log de métricas de recursos do sistema"""
        metrics = {
            "type": "resource_metrics",
            "timestamp": time.time(),
        }
        
        if cpu_percent is not None:
            metrics["cpu_percent"] = cpu_percent
        
        if memory_mb is not None:
            metrics["memory_mb"] = memory_mb
        
        if disk_usage_mb is not None:
            metrics["disk_usage_mb"] = disk_usage_mb
        
        if active_jobs is not None:
            metrics["active_jobs"] = active_jobs
        
        self.logger.info("Resource metrics", extra={"extra_fields": metrics})


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_dir: Path = None,
    enable_file_logging: bool = True,
    enable_correlation_id: bool = True
) -> logging.Logger:
    """
    Configura sistema de logging estruturado
    
    Args:
        log_level: Nível de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Formato dos logs (json, text)
        log_dir: Diretório para arquivos de log
        enable_file_logging: Se deve salvar logs em arquivo
        enable_correlation_id: Se deve incluir correlation ID
    
    Returns:
        Logger configurado
    """
    # Remove handlers existentes
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configuração básica
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Escolhe formatter
    if log_format.lower() == "json":
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s '
            '[%(correlation_id)s] (%(module)s:%(funcName)s:%(lineno)d)'
        )
    
    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    if enable_correlation_id:
        console_handler.addFilter(CorrelationIdFilter())
    
    root_logger.addHandler(console_handler)
    
    # Handler para arquivo (se habilitado)
    if enable_file_logging and log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Log geral
        file_handler = logging.FileHandler(
            log_dir / "audio_normalization.log",
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        
        if enable_correlation_id:
            file_handler.addFilter(CorrelationIdFilter())
        
        root_logger.addHandler(file_handler)
        
        # Log de erro separado
        error_handler = logging.FileHandler(
            log_dir / "errors.log",
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        
        if enable_correlation_id:
            error_handler.addFilter(CorrelationIdFilter())
        
        root_logger.addHandler(error_handler)
    
    return root_logger


def get_correlation_id() -> str:
    """Obtém correlation ID atual ou gera um novo"""
    current_id = correlation_id.get()
    if current_id is None:
        current_id = str(uuid.uuid4())[:8]
        correlation_id.set(current_id)
    return current_id


def set_correlation_id(cid: str = None) -> str:
    """Define correlation ID"""
    if cid is None:
        cid = str(uuid.uuid4())[:8]
    correlation_id.set(cid)
    return cid


def log_with_context(logger: logging.Logger, level: int, message: str, **context):
    """Log com contexto adicional"""
    logger.log(level, message, extra={"extra_fields": context})


# ===== DECORATORS =====
def log_function_call(logger: logging.Logger = None):
    """Decorator para logging de chamadas de função"""
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = logging.getLogger(func.__module__)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            func_name = f"{func.__module__}.{func.__name__}"
            
            logger.debug(
                f"Iniciando {func_name}",
                extra={
                    "extra_fields": {
                        "function": func_name,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys())
                    }
                }
            )
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                logger.debug(
                    f"Concluído {func_name}",
                    extra={
                        "extra_fields": {
                            "function": func_name,
                            "duration_ms": duration_ms,
                            "success": True
                        }
                    }
                )
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                logger.error(
                    f"Erro em {func_name}: {str(e)}",
                    extra={
                        "extra_fields": {
                            "function": func_name,
                            "duration_ms": duration_ms,
                            "success": False,
                            "error": str(e)
                        }
                    }
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            func_name = f"{func.__module__}.{func.__name__}"
            
            logger.debug(
                f"Iniciando {func_name}",
                extra={
                    "extra_fields": {
                        "function": func_name,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys())
                    }
                }
            )
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                logger.debug(
                    f"Concluído {func_name}",
                    extra={
                        "extra_fields": {
                            "function": func_name,
                            "duration_ms": duration_ms,
                            "success": True
                        }
                    }
                )
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                logger.error(
                    f"Erro em {func_name}: {str(e)}",
                    extra={
                        "extra_fields": {
                            "function": func_name,
                            "duration_ms": duration_ms,
                            "success": False,
                            "error": str(e)
                        }
                    }
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def log_execution_time(logger: logging.Logger = None, threshold_ms: float = 1000):
    """Decorator para logging de tempo de execução (apenas se exceder threshold)"""
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = logging.getLogger(func.__module__)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            
            if duration_ms > threshold_ms:
                logger.warning(
                    f"Função lenta detectada: {func.__name__}",
                    extra={
                        "extra_fields": {
                            "function": f"{func.__module__}.{func.__name__}",
                            "duration_ms": duration_ms,
                            "threshold_ms": threshold_ms
                        }
                    }
                )
            
            return result
        
        return wrapper
    
    return decorator


class AuditLogger:
    """Logger especializado para auditoria de segurança"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def log_file_upload(
        self,
        filename: str,
        file_size: int,
        client_ip: str = None,
        user_agent: str = None,
        success: bool = True,
        reason: str = None
    ):
        """Log de upload de arquivo"""
        audit_data = {
            "type": "file_upload",
            "filename": filename,
            "file_size_bytes": file_size,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if reason:
            audit_data["reason"] = reason
        
        level = logging.INFO if success else logging.WARNING
        message = f"File upload {'successful' if success else 'failed'}: {filename}"
        
        self.logger.log(level, message, extra={"extra_fields": audit_data})
    
    def log_security_event(
        self,
        event_type: str,
        severity: str,
        details: Dict[str, Any],
        client_ip: str = None
    ):
        """Log de evento de segurança"""
        audit_data = {
            "type": "security_event",
            "event_type": event_type,
            "severity": severity,
            "details": details,
            "client_ip": client_ip,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.warning(
            f"Security event: {event_type}",
            extra={"extra_fields": audit_data}
        )


# ===== UTILITÁRIOS =====
def create_logger(name: str) -> logging.Logger:
    """Cria logger com configuração padrão"""
    return logging.getLogger(name)


def get_performance_logger() -> PerformanceLogger:
    """Obtém logger de performance"""
    return PerformanceLogger(logging.getLogger("performance"))


def get_audit_logger() -> AuditLogger:
    """Obtém logger de auditoria"""
    return AuditLogger(logging.getLogger("audit"))