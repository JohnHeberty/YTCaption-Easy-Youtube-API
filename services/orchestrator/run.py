"""
Script de inicializacao do orquestrador (legado - use run_new.py)
"""
import uvicorn
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.config import get_settings
from common.log_utils import setup_structured_logging, get_logger

settings = get_settings()

setup_structured_logging(
    service_name="orchestrator",
    log_level="INFO",
)
logger = get_logger(__name__)


def main():
    """Inicia o servidor"""
    logger.info("=" * 80)
    logger.info(f"Starting YouTube Caption Orchestrator API v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Host: {settings.app_host}:{settings.app_port}")
    logger.info(f"Redis: {settings.redis_url}")
    logger.info(f"Workers: {settings.workers}")
    logger.info("=" * 80)

    logger.info("Microservices:")
    logger.info(f"  - Video Downloader: {settings.video_downloader_url}")
    logger.info(f"  - Audio Normalization: {settings.audio_normalization_url}")
    logger.info(f"  - Audio Transcriber: {settings.audio_transcriber_url}")
    logger.info("=" * 80)

    try:
        uvicorn.run(
            "main:app",
            host=settings.app_host,
            port=8000,
            reload=settings.debug,
            workers=settings.workers if not settings.debug else 1,
            log_level="info",
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()