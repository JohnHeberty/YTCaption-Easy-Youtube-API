"""
Structured logging with JSON format and correlation IDs
"""
import logging
import json
import sys
from pathlib import Path
from typing import Optional
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Context var para correlation ID (thread-safe)
_correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


def set_correlation_id(correlation_id: str):
    """Define correlation ID para o contexto atual"""
    _correlation_id.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Obtém correlation ID do contexto atual"""
    return _correlation_id.get()


class JSONFormatter(logging.Formatter):
    """
    Formatter JSON estruturado para logs.
    
    Adiciona automaticamente:
    - Timestamp ISO 8601
    - Correlation ID (se disponível)
    - Informações de contexto (módulo, função, linha)
    - Exception traceback (se presente)
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Adiciona correlation ID se disponível
        cid = get_correlation_id()
        if cid:
            log_data['correlation_id'] = cid
        
        # Adiciona campos extras personalizados
        if hasattr(record, 'job_id'):
            log_data['job_id'] = record.job_id
        if hasattr(record, 'service'):
            log_data['service'] = record.service
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms
        
        # Adiciona exception info se presente
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }
        
        return json.dumps(log_data, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """
    Formatter colorido para console (desenvolvimento).
    """
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'
    }
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Format: [TIME] LEVEL - message
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        message = record.getMessage()
        
        # Adiciona correlation ID se disponível
        cid = get_correlation_id()
        cid_str = f" [{cid[:8]}]" if cid else ""
        
        # Adiciona job_id se disponível
        job_id_str = f" [job:{record.job_id[:8]}]" if hasattr(record, 'job_id') else ""
        
        formatted = f"[{timestamp}]{cid_str}{job_id_str} {color}{record.levelname:8}{reset} - {message}"
        
        # Adiciona exception se presente
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"
        
        return formatted


def setup_structured_logging(
    service_name: str,
    log_level: str = "INFO",
    log_dir: str = "./logs",
    enable_console: bool = True,
    enable_file: bool = True,
    json_format: bool = True
):
    """
    Configura logging estruturado para o serviço.
    
    Args:
        service_name: Nome do serviço (usado no nome do arquivo)
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Diretório para arquivos de log
        enable_console: Se True, envia logs para console
        enable_file: Se True, envia logs para arquivo
        json_format: Se True, usa formato JSON; se False, usa formato texto
    
    Examples:
        >>> setup_structured_logging("orchestrator", "INFO")
        >>> logger = get_logger(__name__)
        >>> logger.info("Service started")
    """
    # Remove handlers existentes
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    root_logger.setLevel(logging.DEBUG)
    
    # Cria diretório de logs se não existe
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        
        if json_format:
            console_handler.setFormatter(JSONFormatter())
        else:
            console_handler.setFormatter(ConsoleFormatter())
        
        root_logger.addHandler(console_handler)
    
    # File handlers
    if enable_file:
        if json_format:
            # Um arquivo JSON com todos os logs
            file_handler = RotatingFileHandler(
                log_path / f"{service_name}.json",
                maxBytes=100 * 1024 * 1024,  # 100MB
                backupCount=10,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(JSONFormatter())
            root_logger.addHandler(file_handler)
        else:
            # Arquivos separados por nível
            for level_name, level in [
                ('error', logging.ERROR),
                ('warning', logging.WARNING),
                ('info', logging.INFO),
                ('debug', logging.DEBUG)
            ]:
                handler = RotatingFileHandler(
                    log_path / f"{service_name}_{level_name}.log",
                    maxBytes=50 * 1024 * 1024,  # 50MB
                    backupCount=5,
                    encoding='utf-8'
                )
                handler.setLevel(level)
                handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                ))
                root_logger.addHandler(handler)
    
    # Log inicial
    root_logger.info(
        f"Structured logging initialized",
        extra={
            'service': service_name,
            'log_level': log_level,
            'json_format': json_format
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Obtém logger configurado.
    
    Args:
        name: Nome do logger (geralmente __name__)
    
    Returns:
        Logger configurado
    
    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing job", extra={'job_id': '123'})
    """
    return logging.getLogger(name)
