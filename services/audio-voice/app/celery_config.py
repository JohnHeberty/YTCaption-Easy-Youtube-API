"""
Configuração do Celery para processamento assíncrono
"""
from celery import Celery
from .config import get_settings

settings = get_settings()
celery_config = settings['celery']

# Cria instância Celery
celery_app = Celery(
    'audio_voice_worker',
    broker=celery_config['broker_url'],
    backend=celery_config['result_backend']
)

# Configurações
celery_app.conf.update(
    task_serializer=celery_config['task_serializer'],
    result_serializer=celery_config['result_serializer'],
    accept_content=celery_config['accept_content'],
    timezone=celery_config['timezone'],
    enable_utc=celery_config['enable_utc'],
    task_track_started=celery_config['task_track_started'],
    task_time_limit=celery_config['task_time_limit'],
    task_soft_time_limit=celery_config['task_soft_time_limit'],
    worker_prefetch_multiplier=celery_config['worker_prefetch_multiplier'],
    worker_max_tasks_per_child=celery_config['worker_max_tasks_per_child'],
    
    # Roteamento de tasks
    task_routes={
        'app.celery_tasks.dubbing_task': {'queue': 'audio_voice_queue'},
        'app.celery_tasks.clone_voice_task': {'queue': 'audio_voice_queue'},
    },
    
    # Retry policy
    task_autoretry_for=(Exception,),
    task_max_retries=3,
    task_default_retry_delay=60,  # 1 minuto
    
    # Conexão com broker
    broker_connection_retry_on_startup=True,
)

# ✅ IMPORTANTE: Importa tasks para registrá-las no Celery
# Isso garante que o worker reconheça as tasks ao inicializar
from . import celery_tasks  # noqa: F401
