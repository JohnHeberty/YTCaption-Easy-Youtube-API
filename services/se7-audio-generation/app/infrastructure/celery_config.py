from common.celery_utils import create_celery_app
from common.log_utils import get_logger

logger = get_logger(__name__)

celery_app = create_celery_app(
    "audio_generation",
    task_default_queue="audio_generation_queue",
    task_routes={
        "generate_audio": {"queue": "audio_generation_queue"},
        "cleanup_expired_jobs": {"queue": "audio_generation_queue"},
    },
    task_time_limit=3600,
    task_soft_time_limit=3300,
    timezone="America/Sao_Paulo",
    enable_utc=False,
)

from . import celery_tasks
