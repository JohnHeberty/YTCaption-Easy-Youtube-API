"""
File Logger - Sistema de logging em arquivo para debug detalhado

Salva logs em /app/storage/logs com rotação automática.
Cada job tem seu próprio arquivo de log para facilitar debug.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional


class FileLogger:
    """Gerenciador de logging em arquivo"""
    
    # Diretório de logs
    LOGS_DIR = Path("/app/storage/logs")
    
    # Manter logs dos últimos 7 dias
    MAX_BYTES = 50 * 1024 * 1024  # 50MB por arquivo
    BACKUP_COUNT = 10  # 10 backups
    
    _initialized = False
    _loggers = {}
    
    @classmethod
    def setup(cls):
        """Configurar sistema de logging global"""
        if cls._initialized:
            return
        
        # Criar diretório de logs
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Configurar formato detalhado
        detailed_format = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] [%(funcName)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Handler para arquivo geral (todas as operações)
        general_handler = RotatingFileHandler(
            cls.LOGS_DIR / "make_video_general.log",
            maxBytes=cls.MAX_BYTES,
            backupCount=cls.BACKUP_COUNT,
            encoding='utf-8'
        )
        general_handler.setLevel(logging.DEBUG)
        general_handler.setFormatter(detailed_format)
        
        # Handler para erros críticos
        error_handler = RotatingFileHandler(
            cls.LOGS_DIR / "make_video_errors.log",
            maxBytes=cls.MAX_BYTES,
            backupCount=cls.BACKUP_COUNT,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_format)
        
        # Adicionar handlers ao root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(general_handler)
        root_logger.addHandler(error_handler)
        
        # Também manter stdout/stderr
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        ))
        root_logger.addHandler(console_handler)
        
        cls._initialized = True
        
        logging.info(f"📝 File logging initialized: {cls.LOGS_DIR}")
    
    @classmethod
    def get_job_logger(cls, job_id: str) -> logging.Logger:
        """
        Criar logger específico para um job
        
        Cada job terá seu próprio arquivo de log para debug isolado.
        """
        if not cls._initialized:
            cls.setup()
        
        if job_id in cls._loggers:
            return cls._loggers[job_id]
        
        # Criar logger específico
        logger = logging.getLogger(f"job.{job_id}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = True  # Propagar para root logger também
        
        # Handler para arquivo do job
        job_log_file = cls.LOGS_DIR / f"job_{job_id}.log"
        job_handler = RotatingFileHandler(
            job_log_file,
            maxBytes=cls.MAX_BYTES,
            backupCount=2,
            encoding='utf-8'
        )
        job_handler.setLevel(logging.DEBUG)
        job_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(funcName)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        
        logger.addHandler(job_handler)
        cls._loggers[job_id] = logger
        
        logger.info(f"🎬 JOB LOGGER CREATED: {job_id}")
        logger.info(f"   Log file: {job_log_file}")
        
        return logger
    
    @classmethod
    def cleanup_old_logs(cls, days: int = 7):
        """Limpar logs antigos (executar periodicamente)"""
        if not cls.LOGS_DIR.exists():
            return
        
        cutoff_time = datetime.now().timestamp() - (days * 86400)
        removed_count = 0
        
        for log_file in cls.LOGS_DIR.glob("job_*.log*"):
            if log_file.stat().st_mtime < cutoff_time:
                log_file.unlink()
                removed_count += 1
        
        if removed_count > 0:
            logging.info(f"🗑️  Cleaned up {removed_count} old job logs (>{days} days)")


# Inicializar automaticamente quando módulo for importado
FileLogger.setup()
