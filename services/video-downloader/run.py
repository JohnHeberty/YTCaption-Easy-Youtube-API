#!/usr/bin/env python3
"""
Script de inicialização do serviço
"""
import os
import uvicorn
from app.main import app
from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    port = settings.get('port', 8001)
    host = settings.get('host', '0.0.0.0')
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )