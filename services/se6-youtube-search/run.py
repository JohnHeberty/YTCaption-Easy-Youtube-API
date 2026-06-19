#!/usr/bin/env python3
"""
YouTube Search Service startup script
"""
import uvicorn
from app.core.config import _core
from common.log_utils import setup_structured_logging

if __name__ == "__main__":
    setup_structured_logging(service_name="youtube-search", log_level=_core.log_level)
    uvicorn.run(
        "app.main:app",
        host=_core.host,
        port=_core.port,
        reload=_core.debug,
        log_level=_core.log_level.lower(),
        limit_max_requests=1000,
        limit_concurrency=100,
    )
