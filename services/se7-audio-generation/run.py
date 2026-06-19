#!/usr/bin/env python3
"""Entry point for the Audio Generation Service."""
import uvicorn
from app.core.config import get_settings
from common.log_utils import setup_structured_logging

if __name__ == "__main__":
    settings = get_settings()
    setup_structured_logging(service_name="audio-generation", log_level=settings.log_level)
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
