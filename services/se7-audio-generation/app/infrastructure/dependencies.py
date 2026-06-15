from functools import lru_cache
import os

from common.di import Dep

from app.core.config import get_settings
from app.domain.interfaces import IJobStore, IVoiceStore, IModelManager, ITTSGenerator


def get_settings_dep():
    return get_settings()


@lru_cache(maxsize=1)
def get_job_store() -> IJobStore:
    from app.infrastructure.redis_store import JobRedisStore

    settings = get_settings()
    redis_url = os.getenv("REDIS_URL", settings.redis_url)
    return JobRedisStore(redis_url=redis_url)


@lru_cache(maxsize=1)
def get_voice_store() -> IVoiceStore:
    from app.infrastructure.redis_store import VoiceRedisStore

    settings = get_settings()
    redis_url = os.getenv("REDIS_URL", settings.redis_url)
    return VoiceRedisStore(redis_url=redis_url)


@lru_cache(maxsize=1)
def get_model_manager() -> IModelManager:
    from app.services.model_manager import ChatterboxModelManager

    settings = get_settings()
    return ChatterboxModelManager(
        model_name=settings.model_name,
        model_dir=settings.model_dir,
        device=settings.device,
    )


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
def get_voice_manager():
    from app.services.voice_manager import VoiceProfileManager

    settings = get_settings()
    return VoiceProfileManager(
        store=get_voice_store(),
        voices_dir=settings.voices_dir,
    )


job_store = Dep(get_job_store)
voice_store = Dep(get_voice_store)
model_manager = Dep(get_model_manager)
generator = Dep(get_generator)
voice_manager = Dep(get_voice_manager)
