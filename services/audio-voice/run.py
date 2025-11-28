"""
Entry point para o serviço Audio Voice
"""
import uvicorn
import logging
from app.config import get_settings
from app.cuda_check import check_cuda

# Setup logging antes de importar app
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    settings = get_settings()
    
    # Verificar CUDA no startup
    logger.info("🚀 Starting Audio Voice Service")
    check_cuda()
    
    uvicorn.run(
        "app.main:app",
        host=settings['host'],
        port=settings['port'],
        log_level=settings['log_level'].lower(),
        reload=settings['debug']
    )
