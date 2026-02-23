"""
Run script for Make-Video Service
"""

import os
import uvicorn
from app.main import app

if __name__ == "__main__":
    # Expandir ${DIVISOR} manualmente se necessário
    port = os.getenv("PORT", "8005")
    divisor = os.getenv("DIVISOR", "5")
    
    # Se PORT contém ${DIVISOR}, substituir
    if "${DIVISOR}" in port:
        port = port.replace("${DIVISOR}", divisor)
    
    port = int(port)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
