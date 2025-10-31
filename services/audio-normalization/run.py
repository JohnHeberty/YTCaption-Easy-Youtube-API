#!/usr/bin/env python3
"""
Script de inicialização do serviço de normalização de áudio
"""
import uvicorn
from app.main import app
from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    # Configurar limite de body size baseado no .env
    max_body_size = settings['max_file_size_mb'] * 1024 * 1024
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info",
        # Configurações para arquivos grandes
        limit_max_requests=1000,
        limit_concurrency=100,
        # uvicorn não tem limite de body size próprio, isso é gerenciado pelo FastAPI/Starlette
    )