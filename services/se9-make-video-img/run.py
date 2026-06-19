#!/usr/bin/env python3
"""Entry point for the Make Video IMG Service."""
import uvicorn

from app.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
        workers=settings.workers if settings.environment != "development" else 1,
    )
