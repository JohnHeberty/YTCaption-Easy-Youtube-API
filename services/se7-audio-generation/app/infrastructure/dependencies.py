from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING
import os

from common.di import Dep
from common.redis_utils.resilient_store import ResilientRedisStore

from app.core.config import get_settings
from app.domain.interfaces import IJobStore, IVoiceStore, IModelManager, ITTSGenerator

if TYPE_CHECKING:
    from app.services.voice_manager import VoiceProfileManager


def get_settings_dep() -> AudioGenSettings:
    return get_settings()


@lru_cache(maxsize=1)
def get_redis_store() -> ResilientRedisStore:
    settings = get_settings()
    redis_url = os.getenv("REDIS_URL", settings.redis_url)
    return ResilientRedisStore(redis_url=redis_url)


@lru_cache(maxsize=1)
def get_job_store() -> IJobStore:
    from app.infrastructure.redis_store import JobRedisStore

    return JobRedisStore(redis_store=get_redis_store())


@lru_cache(maxsize=1)
def get_voice_store() -> IVoiceStore:
    from app.infrastructure.redis_store import VoiceRedisStore

    return VoiceRedisStore(redis_store=get_redis_store())


@lru_cache(maxsize=1)
def get_model_manager() -> IModelManager:
    from app.services.model_manager import ChatterboxModelManager

    return ChatterboxModelManager()


@lru_cache(maxsize=1)
def get_generator() -> ITTSGenerator:
    from app.services.generator import TTSGenerator

    settings = get_settings()
    return TTSGenerator(
        model_manager=get_model_manager(),
        job_store=get_job_store(),
        output_dir=settings.output_dir,
        max_text_length=settings.max_text_length,
        chunk_size=settings.chunk_size,
    )


@lru_cache(maxsize=1)
def get_voice_manager() -> VoiceProfileManager:
    from app.services.voice_manager import VoiceProfileManager

    settings = get_settings()
    return VoiceProfileManager(
        store=get_voice_store(),
        voices_dir=settings.voices_dir,
    )


redis_store = Dep(get_redis_store)
job_store = Dep(get_job_store)
voice_store = Dep(get_voice_store)
model_manager = Dep(get_model_manager)
generator = Dep(get_generator)
voice_manager = Dep(get_voice_manager)
