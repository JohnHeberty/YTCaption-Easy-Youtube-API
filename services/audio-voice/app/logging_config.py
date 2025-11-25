"""
Configuração de logging estruturado para o serviço
"""
import logging
import os
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
    
    # Tentar criar diretório de logs (pode falhar se sem permissão em container)
    log_dir = Path("./logs")
    file_logging_enabled = False
    
    try:
        log_dir.mkdir(exist_ok=True, parents=True)
        
        # Verificar se temos permissão de escrita
        if log_dir.exists() and os.access(log_dir, os.W_OK):
            try:
                # Handler para arquivo
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
                file_logging_enabled = True
                
            except (PermissionError, OSError) as e:
                # Falha ao criar arquivo, mas não é crítico
                pass
        
    except (PermissionError, OSError) as e:
        # Falha ao criar diretório, mas não é crítico
        # Logging em stdout ainda funciona
        pass
    
    # Reduz verbosidade de libs externas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"{service_name} logging initialized at {level} level")
    
    if file_logging_enabled:
        logger.info(f"📁 File logging enabled: {log_dir / f'{service_name}.log'}")
    else:
        logger.info(f"📺 File logging disabled (using stdout only - Docker/K8s compatible)")


def get_logger(name: str) -> logging.Logger:
    """
    Retorna logger configurado para um módulo
    
    Args:
        name: Nome do módulo (__name__)
        
    Returns:
        Logger configurado
    """
    return logging.getLogger(name)
