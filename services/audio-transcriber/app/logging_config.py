"""
Logging estruturado para Audio Transcriber Service
Implementação de logging com correlation IDs e performance metrics
"""
import json
import logging
import time
import contextvars
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


# Context variables para correlation IDs thread-safe
correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar('correlation_id', default='')
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar('request_id', default='')


class StructuredFormatter(logging.Formatter):
    """Formatter para logs estruturados em JSON"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Formata record como JSON estruturado"""
        
        # Dados base do log
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'service': 'audio-transcriber'
        }
        
        # Adiciona correlation IDs se disponíveis
        correlation_id = correlation_id_var.get()
        request_id = request_id_var.get()
        
        if correlation_id:
            log_data['correlation_id'] = correlation_id
        
        if request_id:
            log_data['request_id'] = request_id
        
        # Adiciona informações extras se disponíveis
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        # Adiciona informações de exceção
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info)
            }
        
        # Adiciona contexto adicional do record
        extra_keys = set(record.__dict__.keys()) - {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
            'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
            'thread', 'threadName', 'processName', 'process', 'getMessage',
            'exc_info', 'exc_text', 'stack_info', 'extra_fields'
        }
        
        for key in extra_keys:
            if not key.startswith('_'):
                log_data[key] = getattr(record, key)
        
        return json.dumps(log_data, ensure_ascii=False)


class PerformanceLogger:
    """Logger especializado para métricas de performance"""
    
    def __init__(self, logger_name: str = "transcriber.performance"):
        self.logger = logging.getLogger(logger_name)
    
    def log_transcription_performance(
        self,
        operation: str,
        duration: float,
        file_size: Optional[int] = None,
        audio_duration: Optional[float] = None,
        model_name: Optional[str] = None,
        **extra_fields
    ):
        """Log de métricas de performance de transcrição"""
        
        performance_data = {
            'operation': operation,
            'duration_seconds': round(duration, 3),
            'performance_category': 'transcription'
        }
        
        if file_size:
            performance_data['file_size_bytes'] = file_size
            performance_data['processing_speed_mb_per_sec'] = round(
                (file_size / (1024 * 1024)) / max(duration, 0.001), 3
            )
        
        if audio_duration:
            performance_data['audio_duration_seconds'] = round(audio_duration, 2)
            performance_data['real_time_factor'] = round(
                audio_duration / max(duration, 0.001), 3
            )
        
        if model_name:
            performance_data['whisper_model'] = model_name
        
        # Adiciona campos extras
        performance_data.update(extra_fields)
        
        # Log com nível INFO
        self.logger.info(
            f"Transcription performance: {operation}",
            extra={'extra_fields': performance_data}
        )
    
    def log_resource_usage(
        self,
        operation: str,
        cpu_percent: Optional[float] = None,
        memory_mb: Optional[float] = None,
        gpu_memory_mb: Optional[float] = None,
        **extra_fields
    ):
        """Log de uso de recursos"""
        
        resource_data = {
            'operation': operation,
            'performance_category': 'resources'
        }
        
        if cpu_percent is not None:
            resource_data['cpu_percent'] = round(cpu_percent, 2)
        
        if memory_mb is not None:
            resource_data['memory_mb'] = round(memory_mb, 2)
        
        if gpu_memory_mb is not None:
            resource_data['gpu_memory_mb'] = round(gpu_memory_mb, 2)
        
        resource_data.update(extra_fields)
        
        self.logger.info(
            f"Resource usage: {operation}",
            extra={'extra_fields': resource_data}
        )


class AuditLogger:
    """Logger para eventos de auditoria e segurança"""
    
    def __init__(self, logger_name: str = "transcriber.audit"):
        self.logger = logging.getLogger(logger_name)
    
    def log_file_upload(
        self,
        file_name: str,
        file_size: int,
        client_ip: str,
        user_agent: Optional[str] = None,
        **extra_fields
    ):
        """Log de upload de arquivo"""
        
        audit_data = {
            'event': 'file_upload',
            'file_name': file_name,
            'file_size_bytes': file_size,
            'client_ip': client_ip,
            'audit_category': 'file_operation'
        }
        
        if user_agent:
            audit_data['user_agent'] = user_agent
        
        audit_data.update(extra_fields)
        
        self.logger.info(
            f"File uploaded: {file_name}",
            extra={'extra_fields': audit_data}
        )
    
    def log_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        client_ip: Optional[str] = None,
        **extra_fields
    ):
        """Log de evento de segurança"""
        
        security_data = {
            'event': event_type,
            'severity': severity,
            'description': description,
            'audit_category': 'security'
        }
        
        if client_ip:
            security_data['client_ip'] = client_ip
        
        security_data.update(extra_fields)
        
        # Usa WARNING para eventos de segurança
        self.logger.warning(
            f"Security event: {event_type}",
            extra={'extra_fields': security_data}
        )
    
    def log_transcription_job(
        self,
        job_id: str,
        status: str,
        language: str,
        output_format: str,
        duration: Optional[float] = None,
        **extra_fields
    ):
        """Log de job de transcrição"""
        
        job_data = {
            'event': 'transcription_job',
            'job_id': job_id,
            'status': status,
            'language': language,
            'output_format': output_format,
            'audit_category': 'job_lifecycle'
        }
        
        if duration:
            job_data['processing_duration'] = round(duration, 3)
        
        job_data.update(extra_fields)
        
        self.logger.info(
            f"Transcription job {status}: {job_id}",
            extra={'extra_fields': job_data}
        )


def setup_logging(log_level: str = "INFO", log_file: Optional[Path] = None):
    """
    Configura logging estruturado para a aplicação
    
    Args:
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR)
        log_file: Arquivo para salvar logs (opcional)
    """
    
    # Remove handlers existentes
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configura formatter estruturado
    formatter = StructuredFormatter()
    
    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Handler para arquivo se especificado
    handlers = [console_handler]
    
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    # Configura logging básico
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers,
        force=True
    )
    
    # Reduz verbosidade de bibliotecas externas
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Obtém logger configurado
    
    Args:
        name: Nome do logger
        
    Returns:
        logging.Logger: Logger configurado
    """
    return logging.getLogger(name)


def set_correlation_id(correlation_id: str):
    """Define correlation ID para o contexto atual"""
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> str:
    """Obtém correlation ID do contexto atual"""
    return correlation_id_var.get()


def set_request_id(request_id: str):
    """Define request ID para o contexto atual"""
    request_id_var.set(request_id)


def get_request_id() -> str:
    """Obtém request ID do contexto atual"""
    return request_id_var.get()