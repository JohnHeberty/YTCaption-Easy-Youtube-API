#!/usr/bin/env python3
"""
Script de inicialização do serviço de transcrição de áudio
"""
import os, uvicorn
from app.main import app

if __name__ == "__main__":
    reload_flag = os.getenv("UVICORN_RELOAD", "0") in ("1", "true", "True")
    workers = int(os.getenv("UVICORN_WORKERS", "1"))  # fastapi single-worker + GPU
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8003,
        reload=reload_flag,
        log_level="info",
        workers=workers if not reload_flag else 1,
    )
