import os
from celery import Celery


# Configuração do Redis/Celery via .env
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
celery_broker = os.getenv('CELERY_BROKER_URL', redis_url)
celery_backend = os.getenv('CELERY_RESULT_BACKEND', redis_url)

# Timeouts configuráveis
task_time_limit = int(os.getenv('CELERY_TASK_TIME_LIMIT', '1800'))
task_soft_time_limit = int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', '1500'))

# TTL dos resultados (baseado em CACHE__TTL_HOURS)
cache_ttl_hours = int(os.getenv('CACHE__TTL_HOURS', '24'))
result_expires = cache_ttl_hours * 3600

# Inicializa Celery
celery_app = Celery(
    'audio_normalization_tasks',
    broker=celery_broker,
    backend=celery_backend
)

# Configurações
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    # TTL dos resultados (configurável via CACHE__TTL_HOURS)
    result_expires=result_expires,
    # Timeout das tasks (configurável via .env)
    task_time_limit=task_time_limit,
    task_soft_time_limit=task_soft_time_limit,
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    broker_connection_retry_on_startup=True,
    # 🔧 FILA DEDICADA para audio-normalization
    task_default_queue='audio_normalization_queue',
    task_routes={
        'normalize_audio_task': {'queue': 'audio_normalization_queue'},
        'cleanup_expired_jobs': {'queue': 'audio_normalization_queue'},
    },
    # Auto-discovery das tasks
    include=['app.celery_tasks']
)
