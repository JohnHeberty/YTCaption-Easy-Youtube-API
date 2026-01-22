#!/usr/bin/env python3
"""
Script de inicialização do serviço de normalização de áudio
"""
import uvicorn
from app.main import app
from app.config import get_settings

if __name__ == "__main__":
    import os
    settings = get_settings()
    # Configurar limite de body size baseado no .env
    max_body_size = settings['max_file_size_mb'] * 1024 * 1024
    
    # Porta do .env ou 8001 como padrão
    port = int(os.getenv('PORT', 8001))
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # CORRIGIDO: Desabilita reload em produção
        log_level="info",
        # Configurações para arquivos grandes
        limit_max_requests=1000,
        limit_concurrency=100,
    )