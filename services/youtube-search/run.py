#!/usr/bin/env python3
"""
YouTube Search Service startup script
"""
import uvicorn
from app.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    
    uvicorn.run(
        "app.main:app",
        host=settings['host'],
        port=settings['port'],
        reload=settings['debug'],
        log_level=settings['log_level'].lower(),
        limit_max_requests=1000,
        limit_concurrency=100,
    )
