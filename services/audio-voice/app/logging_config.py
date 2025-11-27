"""
Advanced logging configuration with level separation and FULL RESILIENCE
"""
import logging
import sys
import os
import warnings
from pathlib import Path
from logging.handlers import RotatingFileHandler


def _suppress_noisy_loggers():
    """
    Suprime logs verbosos de bibliotecas externas
    Mantém apenas logs WARNING+ de libs e INFO+ da app
    """
    # Bibliotecas com DEBUG/INFO excessivo
    noisy_loggers = [
        'numba',
        'numba.core',
        'numba.core.ssa',
        'numba.core.byteflow',
        'numba.core.interpreter',
        'matplotlib',
        'matplotlib.font_manager',
        'matplotlib.pyplot',
        'PIL',
        'urllib3',
        'urllib3.connectionpool',
        'requests',
        'multipart',
        'multipart.multipart',
        'TTS',
        'TTS.tts',
        'TTS.api',
        'trainer',
    ]
    
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    # Suprime warnings conhecidos de bibliotecas externas
    warnings.filterwarnings('ignore', category=FutureWarning, module='transformers')
    warnings.filterwarnings('ignore', category=FutureWarning, module='torch')
    warnings.filterwarnings('ignore', category=UserWarning, module='jieba')
    warnings.filterwarnings('ignore', category=UserWarning, module='TTS')
    warnings.filterwarnings('ignore', message='.*pkg_resources.*')
    warnings.filterwarnings('ignore', message='.*weights_only.*')
    warnings.filterwarnings('ignore', message='.*_pytree.*')


def setup_logging(service_name: str = "audio-voice", log_level: str = "DEBUG"):
    """
    Configure logging with separate files for each level.
    RESILIENT: API continues running even if file logging fails.
    """
    log_dir = Path("./logs")
    
    # Try to create log directory with proper permissions
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        # Try to set permissions (777 for maximum compatibility)
        try:
            os.chmod(log_dir, 0o777)
        except Exception:
            pass  # Permission change might fail, but we continue
    except Exception as e:
        print(f"⚠️  WARNING: Could not create log directory {log_dir}: {e}", file=sys.stderr)
        print(f"💡 Suggestion: Run 'chmod 777 {log_dir.absolute()}' to fix permissions", file=sys.stderr)
        print("✅ API will continue with CONSOLE LOGGING ONLY", file=sys.stderr)
    
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
    
    # RESILIENT: Try to add file handlers, but don't crash if they fail
    file_handlers_ok = 0
    file_handlers_failed = 0
    
    # Error handler
    try:
        error_handler = RotatingFileHandler(log_dir / 'error.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        logger.addHandler(error_handler)
        file_handlers_ok += 1
    except Exception as e:
        print(f"⚠️  WARNING: Could not create error.log: {e}", file=sys.stderr)
        print(f"💡 Suggestion: Run 'chmod 777 {log_dir.absolute()}' to fix permissions", file=sys.stderr)
        file_handlers_failed += 1
    
    # Warning handler
    try:
        warning_handler = RotatingFileHandler(log_dir / 'warning.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        warning_handler.setLevel(logging.WARNING)
        warning_handler.setFormatter(file_formatter)
        logger.addHandler(warning_handler)
        file_handlers_ok += 1
    except Exception as e:
        print(f"⚠️  WARNING: Could not create warning.log: {e}", file=sys.stderr)
        file_handlers_failed += 1
    
    # Info handler
    try:
        info_handler = RotatingFileHandler(log_dir / 'info.log', maxBytes=20*1024*1024, backupCount=10, encoding='utf-8')
        info_handler.setLevel(logging.INFO)
        info_handler.setFormatter(file_formatter)
        logger.addHandler(info_handler)
        file_handlers_ok += 1
    except Exception as e:
        print(f"⚠️  WARNING: Could not create info.log: {e}", file=sys.stderr)
        file_handlers_failed += 1
    
    # Debug handler
    try:
        debug_handler = RotatingFileHandler(log_dir / 'debug.log', maxBytes=50*1024*1024, backupCount=3, encoding='utf-8')
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(file_formatter)
        logger.addHandler(debug_handler)
        file_handlers_ok += 1
    except Exception as e:
        print(f"⚠️  WARNING: Could not create debug.log: {e}", file=sys.stderr)
        file_handlers_failed += 1
    
    # Console handler - ALWAYS WORKS
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Suppress noisy DEBUG loggers from external libraries
    _suppress_noisy_loggers()
    
    # Report logging status
    if file_handlers_ok == 4:
        logging.info(f"✅ Logging system started for {service_name}")
        logging.info(f"📁 Files: error.log | warning.log | info.log | debug.log")
    elif file_handlers_ok > 0:
        logging.warning(f"⚠️  Logging partially initialized for {service_name}")
        logging.warning(f"✅ {file_handlers_ok} file handlers OK | ❌ {file_handlers_failed} failed")
        logging.warning(f"💡 Run 'chmod 777 {log_dir.absolute()}' to enable all file logging")
    else:
        logging.warning(f"⚠️  Logging running in CONSOLE-ONLY mode for {service_name}")
        logging.warning(f"❌ All file handlers failed (permission denied)")
        logging.warning(f"💡 Run 'chmod 777 {log_dir.absolute()}' to enable file logging")
        logging.warning("✅ API continues running normally with console logging")


def get_logger(name: str = None) -> logging.Logger:
    """
    Retorna logger configurado
    
    Args:
        name: Nome do logger (opcional)
    
    Returns:
        Logger configurado
    """
    return logging.getLogger(name or __name__)


def log_job_serialization(job, stage: str, logger):
    """Helper para log detalhado de serialização de Job"""
    logger.debug(f"📦 Job Serialization [{stage}]:")
    logger.debug(f"  - id: {job.id}")
    logger.debug(f"  - mode: {job.mode}")
    logger.debug(f"  - status: {job.status}")
    logger.debug(f"  - input_file: {job.input_file}")
    logger.debug(f"  - output_file: {job.output_file}")
    logger.debug(f"  - text: {job.text[:50] if job.text else None}...")
    logger.debug(f"  - voice_name: {job.voice_name}")


def log_dict_serialization(job_dict: dict, stage: str, logger):
    """Helper para log detalhado de dict"""
    logger.debug(f"📦 Dict Serialization [{stage}]:")
    logger.debug(f"  - id: {job_dict.get('id')}")
    logger.debug(f"  - mode: {job_dict.get('mode')}")
    logger.debug(f"  - input_file: {job_dict.get('input_file')}")
    logger.debug(f"  - Keys: {list(job_dict.keys())}")