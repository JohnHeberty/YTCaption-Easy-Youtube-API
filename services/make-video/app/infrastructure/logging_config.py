"""
Logging Configuration
"""
import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    service_name: str = "make-video",
    log_level: str = "INFO",
    log_dir: Optional[str] = None,
    json_format: bool = True
) -> None:
    """
    Configura logging do serviço
    
    Args:
        service_name: Nome do serviço
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR)
        log_dir: Diretório para arquivos de log
        json_format: Se True, usa formato JSON
    """
    
    # Criar diretório de logs se especificado
    if log_dir:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Formato de log
    if json_format:
        log_format = '{"time": "%(asctime)s", "service": "' + service_name + '", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}'
    else:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Configurar handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # Configurar logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.addHandler(console_handler)
    
    # Handler para arquivo se log_dir especificado
    if log_dir:
        file_handler = logging.FileHandler(
            Path(log_dir) / f"{service_name}.log"
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(file_handler)
    
    # Silenciar logs muito verbosos
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """
    Retorna logger configurado
    
    Args:
        name: Nome do logger (geralmente __name__)
    
    Returns:
        Logger configurado
    """
    return logging.getLogger(name)
