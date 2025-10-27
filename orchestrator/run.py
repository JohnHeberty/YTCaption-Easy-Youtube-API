"""
Script de inicialização do orquestrador
"""
import uvicorn
import logging
from pathlib import Path
import sys

# Adiciona diretório ao path
sys.path.insert(0, str(Path(__file__).parent))

from modules.config import get_orchestrator_settings

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/orchestrator.log')
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Inicia o servidor"""
    settings = get_orchestrator_settings()
    
    logger.info("=" * 80)
    logger.info(f"Starting YouTube Caption Orchestrator API v{settings['app_version']}")
    logger.info(f"Environment: {settings['environment']}")
    logger.info(f"Host: {settings['app_host']}:{settings['app_port']}")
    logger.info(f"Redis: {settings['redis_url']}")
    logger.info(f"Workers: {settings['workers']}")
    logger.info("=" * 80)
    
    # Microserviços
    logger.info("Microservices:")
    logger.info(f"  - Video Downloader: {settings['video_downloader_url']}")
    logger.info(f"  - Audio Normalization: {settings['audio_normalization_url']}")
    logger.info(f"  - Audio Transcriber: {settings['audio_transcriber_url']}")
    logger.info("=" * 80)
    
    try:
        uvicorn.run(
            "main:app",
            host=settings["app_host"],
            port=settings["app_port"],
            reload=settings["debug"],
            workers=settings["workers"] if not settings["debug"] else 1,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
