#!/usr/bin/env python3
"""
Script de inicialização do serviço de normalização de áudio
Versão 2.0 com alta resiliência e observabilidade completa
"""
import os
import sys
import uvicorn
from pathlib import Path

# Adiciona app ao path para imports
sys.path.insert(0, str(Path(__file__).parent))

from app.main import app_normalization
from app.config import get_settings
from app.logging_config import create_logger

logger = create_logger(__name__)


def main():
    """Função principal de inicialização"""
    try:
        # Carrega configurações
        settings = get_settings()
        
        logger.info(f"🚀 Iniciando {settings.app_name} v{settings.version}")
        logger.info(f"📊 Ambiente: {settings.environment}")
        logger.info(f"🔧 Debug: {'habilitado' if settings.debug else 'desabilitado'}")
        
        # Verifica configuração de instrumentação
        if settings.monitoring.enable_tracing:
            logger.info("📡 Instrumentação distribuída habilitada")
            if settings.monitoring.jaeger_endpoint:
                logger.info(f"🔍 Jaeger endpoint: {settings.monitoring.jaeger_endpoint}")
        
        # Inicia servidor
        uvicorn.run(
            app_normalization,
            host=settings.host,
            port=settings.port,
            log_level="info" if not settings.debug else "debug",
            access_log=True,
            reload=settings.debug and settings.environment == "development"
        )
        
    except Exception as e:
        logger.error(f"❌ Falha na inicialização: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
