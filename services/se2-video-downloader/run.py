#!/usr/bin/env python3
"""
Script de inicialização do serviço
"""
import uvicorn
from app.main import app
from app.core.config import get_settings
from common.log_utils import setup_structured_logging

if __name__ == "__main__":
    settings = get_settings()
    setup_structured_logging(service_name="video-downloader", log_level=settings.log_level)
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        workers=1,
        limit_max_requests=10_000,
        limit_concurrency=30,
    )