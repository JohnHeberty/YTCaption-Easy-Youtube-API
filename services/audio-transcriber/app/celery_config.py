import os
from celery import Celery

# Configuração do Redis
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Inicializa Celery
celery_app = Celery(
    'audio_normalization_tasks',
    broker=redis_url,
    backend=redis_url
)

# Configurações
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # TTL dos resultados (24 horas)
    result_expires=86400,
    
    # Timeout das tasks (30 minutos)
    task_time_limit=1800,
    task_soft_time_limit=1600,
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)
