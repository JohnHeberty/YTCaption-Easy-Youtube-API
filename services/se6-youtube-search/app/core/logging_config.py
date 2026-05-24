"""
Backward-compatible logging configuration.
Delegates to common.log_utils for structured logging.
"""
import logging
from common.log_utils import setup_structured_logging as _setup, get_logger as _get_logger


def setup_logging(service_name: str = "youtube-search", log_level: str = "INFO"):
    """Configure logging - delegates to common.log_utils.setup_structured_logging"""
    _setup(service_name=service_name, log_level=log_level, json_format=False)


def get_logger(name: str) -> logging.Logger:
    """Get logger - delegates to common.log_utils.get_logger"""
    return _get_logger(name)