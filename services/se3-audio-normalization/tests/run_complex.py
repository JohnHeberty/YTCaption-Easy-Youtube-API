#!/usr/bin/env python3
"""
Script de inicialização do serviço de normalização de áudio
Versão 2.0 com alta resiliência e observabilidade completa
"""
import os
import sys
import uvicorn
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings

settings = get_settings()


def main():
    """Função principal de inicialização"""
    try:
        print(f"Iniciando {settings['app_name']} v{settings['version']}")
        print(f"Ambiente: {settings['environment']}")
        print(f"Debug: {'habilitado' if settings['debug'] else 'desabilitado'}")

        uvicorn.run(
            "app.main:app",
            host=settings['host'],
            port=settings['port'],
            log_level="info" if not settings['debug'] else "debug",
            access_log=True,
            reload=settings['debug'] and settings['environment'] == 'development'
        )

    except Exception as e:
        print(f"Falha na inicialização: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()