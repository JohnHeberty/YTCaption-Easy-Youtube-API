"""Global service instances management."""
from __future__ import annotations

from typing import Any

from ..core.config import get_settings
from .redis_store import MakeVideoJobStore as RedisJobStore
from ..api.api_client import MicroservicesClient
from ..services.video_builder import VideoBuilder
from ..services.shorts_manager import ShortsCache
from ..services.subtitle_generator import SubtitleGenerator
from ..video_processing.video_validator import VideoValidator
from ..services.blacklist_factory import get_blacklist
from ..core.constants import ValidationThresholds
from common.log_utils import get_logger

logger = get_logger(__name__)

# Global instances (will be initialized per worker)
redis_store = None
api_client = None
video_builder = None
shorts_cache = None
subtitle_gen = None
video_validator = None
blacklist = None


def get_instances() -> tuple[Any, Any, Any, Any, Any]:
    """Inicializa instâncias globais se necessário"""
    global redis_store, api_client, video_builder, shorts_cache, subtitle_gen, video_validator, blacklist

    if redis_store is None:
        settings = get_settings()
        redis_store = RedisJobStore(redis_url=settings['redis_url'])

        api_client = MicroservicesClient(
            youtube_search_url=settings['youtube_search_url'],
            video_downloader_url=settings['video_downloader_url'],
            audio_transcriber_url=settings['audio_transcriber_url'],
            api_key=settings.get('api_key'),
        )

        video_builder = VideoBuilder(
            output_dir=settings['output_dir'],
            video_codec=settings['ffmpeg_video_codec'],
            audio_codec=settings['ffmpeg_audio_codec'],
            preset=settings['ffmpeg_preset'],
            crf=settings['ffmpeg_crf']
        )

        shorts_cache = ShortsCache(
            cache_dir=settings['shorts_cache_dir']
        )

        subtitle_gen = SubtitleGenerator()

        video_validator = VideoValidator(
            min_confidence=ValidationThresholds.OCR_MIN_CONFIDENCE,
            frames_per_second=settings.get('ocr_frames_per_second', 3),
            max_frames=settings.get('ocr_max_frames', 240),
            redis_store=redis_store
        )
        blacklist = get_blacklist()

        logger.info("✅ Video validator and blacklist initialized")

    return redis_store, api_client, video_builder, shorts_cache, subtitle_gen
