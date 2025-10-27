"""
Advanced logging configuration with level separation
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logging(service_name: str = "audio-transcriber", log_level: str = "INFO"):
    """Configure logging with separate files for each level"""
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)
    
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    error_handler = RotatingFileHandler(log_dir / 'error.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    logger.addHandler(error_handler)
    
    warning_handler = RotatingFileHandler(log_dir / 'warning.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    warning_handler.setLevel(logging.WARNING)
    warning_handler.setFormatter(file_formatter)
    logger.addHandler(warning_handler)
    
    info_handler = RotatingFileHandler(log_dir / 'info.log', maxBytes=20*1024*1024, backupCount=10, encoding='utf-8')
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(file_formatter)
    logger.addHandler(info_handler)
    
    debug_handler = RotatingFileHandler(log_dir / 'debug.log', maxBytes=50*1024*1024, backupCount=3, encoding='utf-8')
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(file_formatter)
    logger.addHandler(debug_handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    logging.info(f"Logging system started for {service_name}")
    logging.info(f"Files: error.log | warning.log | info.log | debug.log")


def get_logger(name: str = None) -> logging.Logger:
    """
    Retorna logger configurado
    
    Args:
        name: Nome do logger (opcional)
    
    Returns:
        Logger configurado
    """
    return logging.getLogger(name or __name__)