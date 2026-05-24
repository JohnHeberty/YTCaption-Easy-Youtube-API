"""
Celery configuration for audio-transcriber service.

Uses the shared create_celery_app factory for consistent config.
"""
from common.celery_utils import create_celery_app
from common.log_utils import get_logger

logger = get_logger(__name__)

celery_app = create_celery_app(
    "audio_transcriber",
    task_default_queue="audio_transcriber_queue",
    task_routes={
        "transcribe_audio": {"queue": "audio_transcriber_queue"},
        "cleanup_expired_jobs": {"queue": "audio_transcriber_queue"},
        "cleanup_orphan_jobs": {"queue": "audio_transcriber_queue"},
    },
    task_time_limit=3600,
    task_soft_time_limit=3300,
    timezone="America/Sao_Paulo",
    enable_utc=False,
)

# Configuração do Celery Beat para tarefas periódicas
try:
    from .celery_beat_config import get_beat_schedule  # noqa: E402
    celery_app.conf.beat_schedule = get_beat_schedule()
    logger.info("Celery Beat schedule configurado")
except Exception as e:
    logger.warning(f"Celery Beat schedule nao configurado: {e}")

# Importa tasks para registro no Celery
from . import celery_tasks  # noqa: E402, F401
