from common.celery_utils import create_celery_app
from common.log_utils import get_logger

logger = get_logger(__name__)

celery_app = create_celery_app(
    "image_generation",
    task_default_queue="image_generation_queue",
    task_routes={
        "app.infrastructure.celery_tasks.generate_image": {"queue": "image_generation_queue"},
        "app.infrastructure.celery_tasks.cleanup_expired_jobs": {"queue": "image_generation_queue"},
    },
    task_time_limit=600,
    task_soft_time_limit=540,
    timezone="America/Sao_Paulo",
    enable_utc=False,
)

from . import celery_tasks
