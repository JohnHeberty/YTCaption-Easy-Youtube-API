"""
Configuração simples e eficaz de logging
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logging(service_name: str = "audio-normalization", log_level: str = "INFO"):
    """
    Configura logging simples para o serviço
    
    Args:
        service_name: Nome do serviço
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR)
    """
    # Cria diretório de logs
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)
    
    # Arquivo de log com timestamp
    log_file = log_dir / f"{service_name}.log"
    
    # Configuração do logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove handlers existentes
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Formato de log
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Handler para arquivo (com rotação)
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    logging.info(f"Logging configurado para {service_name} - Nível: {log_level}")
    logging.info(f"Logs salvos em: {log_file}")


def get_logger(name: str = None) -> logging.Logger:
    """
    Retorna logger configurado
    
    Args:
        name: Nome do logger (opcional)
    
    Returns:
        Logger configurado
    """
    return logging.getLogger(name or __name__)