"""
Configuração de logging estruturado para o serviço
"""
import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(service_name: str = "audio-voice", level: str = "INFO"):
    """
    Configura logging estruturado para o serviço
    
    Args:
        service_name: Nome do serviço para identificação nos logs
        level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Formato de log estruturado
    log_format = (
        "[%(asctime)s] %(levelname)-8s "
        "[%(name)s:%(funcName)s:%(lineno)d] "
        "%(message)s"
    )
    
    # Configuração do logger root
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    
    # Cria diretório de logs se não existir
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True, parents=True)
    
    # Handler para arquivo (opcional, pode ser desabilitado em produção se usar agregador)
    file_handler = logging.FileHandler(
        log_dir / f"{service_name}.log",
        mode='a',
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format))
    
    # Adiciona handler de arquivo ao root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    
    # Reduz verbosidade de libs externas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"{service_name} logging initialized at {level} level")


def get_logger(name: str) -> logging.Logger:
    """
    Retorna logger configurado para um módulo
    
    Args:
        name: Nome do módulo (__name__)
        
    Returns:
        Logger configurado
    """
    return logging.getLogger(name)
