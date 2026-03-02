#!/usr/bin/env python3
"""
Script de inicialização do serviço
"""
import os
import uvicorn
from app.main import app
from app.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    port = settings.get('port', 8000)
    host = settings.get('host', '0.0.0.0')
    debug = settings.get('debug', False)
    log_level = settings.get('log_level', 'INFO').lower()

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level=log_level,
        workers=1,
        limit_max_requests=10_000,
        limit_concurrency=30,
    )