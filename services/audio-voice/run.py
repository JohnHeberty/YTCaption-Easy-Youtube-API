"""
Entry point para o serviço Audio Voice
"""
import uvicorn
from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    
    uvicorn.run(
        "app.main:app",
        host=settings['host'],
        port=settings['port'],
        log_level=settings['log_level'].lower(),
        reload=settings['debug']
    )
