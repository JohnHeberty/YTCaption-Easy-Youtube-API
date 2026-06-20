"""
Exception handling utilities
"""
from __future__ import annotations

from common.exceptions import ServiceError
from .handlers import (
    BaseServiceException,
    ValidationException,
    ResourceNotFoundException,
    ProcessingException,
    ServiceUnavailableException,
    RateLimitException,
    create_exception_handler,
    setup_exception_handlers,
)

__all__ = [
    'ServiceError',
    'BaseServiceException',
    'ValidationException',
    'ResourceNotFoundException',
    'ProcessingException',
    'ServiceUnavailableException',
    'RateLimitException',
    'create_exception_handler',
    'setup_exception_handlers',
]
