"""
Script de inicialização do orquestrador (versão refatorada).

Usa a nova arquitetura com injeção de dependência.
"""
import sys
from pathlib import Path

# Adiciona diretório ao path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import uvicorn
    from common.log_utils import get_logger
    from core.config import get_settings

    logger = get_logger(__name__)

    def main():
        """Inicia o servidor."""
        settings = get_settings()

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
                port=settings.app_port,
                reload=settings.debug,
                workers=settings.workers if not settings.debug else 1,
                log_level="info",
            )
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            sys.exit(1)

    if __name__ == "__main__":
        main()

except ImportError as e:
    print(f"Import error: {e}")
    print("Cannot start orchestrator - check dependencies and .env configuration.")
    sys.exit(1)
