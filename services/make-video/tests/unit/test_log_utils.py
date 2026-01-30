"""
Testes para log_utils
"""

import pytest
import json
from app.log_utils import ContextLogger, StructuredFormatter, setup_logging
import logging


def test_context_logger_info():
    """Testa logging com contexto"""
    logger = ContextLogger('test')
    
    # Não deve levantar exceção
    logger.info("test_message", key1="value1", key2=123)


def test_structured_formatter():
    """Testa formatter estruturado"""
    formatter = StructuredFormatter()
    record = logging.LogRecord(
        name='test',
        level=logging.INFO,
        pathname='test.py',
        lineno=10,
        msg='Test message',
        args=(),
        exc_info=None
    )
    
    formatted = formatter.format(record)
    
    # Deve ser JSON válido
    data = json.loads(formatted)
    
    assert 'timestamp' in data
    assert data['level'] == 'INFO'
    assert data['message'] == 'Test message'
    assert data['logger'] == 'test'


def test_setup_logging():
    """Testa setup de logging"""
    setup_logging(level='DEBUG', structured=True)
    
    # Verificar que root logger foi configurado
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) > 0
