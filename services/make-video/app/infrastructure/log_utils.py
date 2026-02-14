"""
Logging estruturado com contexto

Implementa logging JSON com campos estruturados para facilitar análise
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class StructuredFormatter(logging.Formatter):
    """
    Formatter que produz logs em JSON estruturado
    
    Adiciona campos padrão: timestamp, level, message, context
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # Adicionar campos extras se existirem
        if hasattr(record, 'context'):
            log_data['context'] = record.context
        
        # Adicionar exception info se existir
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class ContextLogger:
    """
    Logger com suporte a contexto estruturado
    
    Exemplo:
        logger = ContextLogger(__name__)
        logger.info("processing_video", video_id="abc123", duration=45.5)
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def _log(self, level: int, message: str, **context):
        """Log interno com contexto"""
        extra = {'context': context} if context else {}
        self.logger.log(level, message, extra=extra)
    
    def debug(self, message: str, **context):
        self._log(logging.DEBUG, message, **context)
    
    def info(self, message: str, **context):
        self._log(logging.INFO, message, **context)
    
    def warning(self, message: str, **context):
        self._log(logging.WARNING, message, **context)
    
    def error(self, message: str, **context):
        self._log(logging.ERROR, message, **context)
    
    def critical(self, message: str, **context):
        self._log(logging.CRITICAL, message, **context)


def setup_logging(level: str = 'INFO', structured: bool = True):
    """
    Configura logging global
    
    Args:
        level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        structured: Se True, usa formato JSON estruturado
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configurar handler
    handler = logging.StreamHandler(sys.stdout)
    
    if structured:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        )
    
    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []  # Limpar handlers existentes
    root_logger.addHandler(handler)
    
    # Silenciar logs muito verbosos de bibliotecas
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


# Instância global para facilitar uso
def get_logger(name: str) -> ContextLogger:
    """Retorna logger estruturado"""
    return ContextLogger(name)
