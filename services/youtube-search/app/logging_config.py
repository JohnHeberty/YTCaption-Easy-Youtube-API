"""
Advanced logging configuration with level separation and full resilience
"""
import logging
import sys
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logging(service_name: str = "youtube-search", log_level: str = "INFO"):
    """
    Configure logging with separate files for each level.
    RESILIENT: API continues running even if file logging fails.
    """
    log_dir = Path("./logs")
    
    # Try to create log directory with proper permissions
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(log_dir, 0o777)
        except Exception:
            pass
    except Exception as e:
        print(f"⚠️  WARNING: Could not create log directory {log_dir}: {e}", file=sys.stderr)
        print(f"💡 Suggestion: Run 'chmod 777 {log_dir.absolute()}' to fix permissions", file=sys.stderr)
        print("✅ Service will continue with CONSOLE LOGGING ONLY", file=sys.stderr)
    
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
    
    # Try to add file handlers
    try:
        error_handler = RotatingFileHandler(log_dir / 'error.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        logger.addHandler(error_handler)
    except Exception as e:
        print(f"⚠️  WARNING: Could not create error.log: {e}", file=sys.stderr)
    
    try:
        warning_handler = RotatingFileHandler(log_dir / 'warning.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        warning_handler.setLevel(logging.WARNING)
        warning_handler.setFormatter(file_formatter)
        logger.addHandler(warning_handler)
    except Exception as e:
        print(f"⚠️  WARNING: Could not create warning.log: {e}", file=sys.stderr)
    
    try:
        info_handler = RotatingFileHandler(log_dir / 'info.log', maxBytes=20*1024*1024, backupCount=10, encoding='utf-8')
        info_handler.setLevel(logging.INFO)
        info_handler.setFormatter(file_formatter)
        logger.addHandler(info_handler)
    except Exception as e:
        print(f"⚠️  WARNING: Could not create info.log: {e}", file=sys.stderr)
    
    try:
        debug_handler = RotatingFileHandler(log_dir / 'debug.log', maxBytes=50*1024*1024, backupCount=3, encoding='utf-8')
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(file_formatter)
        logger.addHandler(debug_handler)
    except Exception as e:
        print(f"⚠️  WARNING: Could not create debug.log: {e}", file=sys.stderr)
    
    # Console handler (always succeeds)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    logger.info(f"✅ {service_name} logging configured (level: {log_level})")
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get logger instance"""
    return logging.getLogger(name)
