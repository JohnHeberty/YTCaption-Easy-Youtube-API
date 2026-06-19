#!/usr/bin/env python3
"""
Script de inicialização do serviço de transcrição de áudio
"""
import uvicorn
from app.core.config import _core
from common.log_utils import setup_structured_logging

if __name__ == "__main__":
    setup_structured_logging(service_name="audio-transcriber", log_level=_core.log_level)
    uvicorn.run(
        "app.main:app",
        host=_core.host,
        port=_core.port,
        reload=_core.debug,
        log_level=_core.log_level.lower(),
        workers=_core.workers if not _core.debug else 1,
        limit_max_requests=10_000,
        limit_concurrency=20,
        access_log=True,
    )
