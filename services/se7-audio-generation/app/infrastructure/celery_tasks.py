from typing import Optional

from common.log_utils import get_logger
from common.datetime_utils import now_brazil
from celery import Task

from app.domain.models import AudioGenerationJob
from app.infrastructure.celery_config import celery_app
from app.core.constants import CELERY_MAX_RETRIES, CELERY_SOFT_TIME_LIMIT, CELERY_TIME_LIMIT

logger = get_logger(__name__)

CLEANUP_BATCH_SIZE = 100


class GenerationTask(Task):
    _generator = None
    _store = None

    @property
    def store(self):
        if self._store is None:
            from app.infrastructure.dependencies import get_job_store
            self._store = get_job_store()
        return self._store

    @property
    def generator(self):
        if self._generator is None:
            from app.infrastructure.dependencies import get_generator
            self._generator = get_generator()
        return self._generator


def _resolve_audio_prompt_path(voice_id: str, store) -> Optional[str]:
    """Resolve voice_id to audio file path for voice cloning."""
    if not voice_id:
        return None
    try:
        from app.infrastructure.dependencies import get_voice_store
        from app.core.config import get_settings
        from app.services.voice_manager import VoiceProfileManager

        settings = get_settings()
        voice_store = get_voice_store()
        vm = VoiceProfileManager(voice_store, settings.voices_dir)
        return vm.get_profile_audio_path(voice_id)
    except Exception as e:
        logger.warning("Failed to resolve voice profile %s: %s", voice_id, e)
        return None


def _mark_job_failed(job_dict: dict, error_message: str, store) -> None:
    """Mark a job as FAILED in the store."""
    try:
        job = AudioGenerationJob(**job_dict)
        job.mark_as_failed(str(error_message), "TaskError")
        store.update_job(job)
    except Exception as store_err:
        logger.error("Failed to mark job as failed: %s", store_err)


@celery_app.task(
    bind=True,
    base=GenerationTask,
    name="generate_audio",
    autoretry_for=(ConnectionError, IOError, OSError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=CELERY_MAX_RETRIES,
    soft_time_limit=CELERY_SOFT_TIME_LIMIT,
    time_limit=CELERY_TIME_LIMIT,
)
def generate_audio_task(self, job_dict: dict) -> dict:
    job_id = job_dict.get("id", "unknown")
    logger.info("Starting audio generation job %s", job_id)

    try:
        job = AudioGenerationJob(**job_dict)
        audio_prompt_path = _resolve_audio_prompt_path(job.voice_id, self.store)
        if audio_prompt_path:
            logger.info("Using voice profile %s for cloning", job.voice_id)

        result_job = self.generator.generate(job, audio_prompt_path=audio_prompt_path)
        return result_job.model_dump()

    except Exception as e:
        logger.error("Job %s failed in task: %s", job_id, e)
        _mark_job_failed(job_dict, str(e), self.store)
        raise


@celery_app.task(name="cleanup_expired_jobs")
def cleanup_expired_jobs_task():
    from app.infrastructure.dependencies import get_job_store

    store = get_job_store()
    expired = []
    for job in store.list_jobs(CLEANUP_BATCH_SIZE):
        if job.is_expired:
            store.delete_job(job.id)
            expired.append(job.id)
    logger.info("Cleaned up %s expired jobs", len(expired))
    return {"cleaned": len(expired), "jobs": expired}
