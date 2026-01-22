"""
Logging utilities shared across all microservices
"""
from .structured import setup_structured_logging, get_logger, JSONFormatter, set_correlation_id, get_correlation_id

__all__ = [
    'setup_structured_logging',
    'get_logger',
    'JSONFormatter',
    'set_correlation_id',
    'get_correlation_id'
]
