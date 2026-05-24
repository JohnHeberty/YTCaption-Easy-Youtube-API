"""
Run script for Make-Video Service
"""

import os
import uvicorn
from app.main import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8005"))
    reload_flag = os.getenv("UVICORN_RELOAD", "0") in ("1", "true", "True")
    workers = int(os.getenv("UVICORN_WORKERS", "1"))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=reload_flag,
        workers=workers if not reload_flag else 1,
        log_level="info",
        limit_max_requests=1_000,
        limit_concurrency=10,
        access_log=True,
    )
