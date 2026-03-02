#!/usr/bin/env python3
"""
Script de inicialização do serviço de normalização de áudio
"""
import uvicorn
from app.main import app
from app.core.config import get_settings

if __name__ == "__main__":
    import os
    settings = get_settings()
    # Configurar limite de body size baseado no .env (em bytes)
    max_body_size = settings['max_file_size_mb'] * 1024 * 1024
    
    # Porta do .env ou 8002 como padrão
    port = int(os.getenv('PORT', 8003))
    
    # Workers baseado no número de CPUs disponíveis
    workers = int(os.getenv('WORKERS', 1))
    
    print(f"🚀 Iniciando Audio Normalization Service")
    print(f"   Port: {port}")
    print(f"   Workers: {workers}")
    print(f"   Max file size: {settings['max_file_size_mb']}MB")
    print(f"   Max body size: {max_body_size} bytes")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # Desabilita reload em produção
        log_level="info",
        # CRÍTICO: Define limite de body size para aceitar arquivos grandes
        limit_max_requests=1000,
        limit_concurrency=100,
        timeout_keep_alive=300,  # 5 minutos
        h11_max_incomplete_event_size=max_body_size,  # Limite de evento HTTP incompleto
    )