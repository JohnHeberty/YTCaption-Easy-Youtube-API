#!/usr/bin/env python3
"""
Script de inicialização do serviço de normalização de áudio
"""
import uvicorn
from app.main import app
from app.core.config import _core
from common.log_utils import setup_structured_logging

if __name__ == "__main__":
    setup_structured_logging(service_name="audio-normalization", log_level=_core.log_level)

    max_body_size = _core.max_file_size_mb * 1024 * 1024

    uvicorn.run(
        "app.main:app",
        host=_core.host,
        port=_core.port,
        reload=_core.debug,
        log_level=_core.log_level.lower(),
        limit_max_requests=1000,
        limit_concurrency=100,
        timeout_keep_alive=300,
        h11_max_incomplete_event_size=max_body_size,
    )