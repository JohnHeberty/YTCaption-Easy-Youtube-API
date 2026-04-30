import os
from celery import Celery
from common.log_utils import get_logger

logger = get_logger(__name__)

# Configuração do Redis via .env
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
celery_broker = os.getenv('CELERY_BROKER_URL', redis_url)
celery_backend = os.getenv('CELERY_RESULT_BACKEND', redis_url)

# Timeouts configuráveis
task_time_limit = int(os.getenv('CELERY_TASK_TIME_LIMIT', '3600'))  # 1 hora
task_soft_time_limit = int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', '3300'))  # 55 min

# TTL dos resultados (baseado em CACHE_TTL_HOURS)
cache_ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
result_expires = cache_ttl_hours * 3600

# Inicializa Celery
celery_app = Celery(
    'audio_transcriber_tasks',
    broker=celery_broker,
    backend=celery_backend
)

# Configurações
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Sao_Paulo',
    enable_utc=False,
    
    # TTL dos resultados (configurável via CACHE_TTL_HOURS)
    result_expires=result_expires,
    
    # Timeout das tasks (configurável via .env)
    task_time_limit=task_time_limit,
    task_soft_time_limit=task_soft_time_limit,
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    broker_connection_retry_on_startup=True,
    
    # 🔧 FILA DEDICADA para audio-transcriber
    task_default_queue='audio_transcriber_queue',
    task_routes={
        'transcribe_audio': {'queue': 'audio_transcriber_queue'},
        'cleanup_expired_jobs': {'queue': 'audio_transcriber_queue'},
        'cleanup_orphan_jobs': {'queue': 'audio_transcriber_queue'},
    },
)

# ✅ Configuração do Celery Beat para tarefas periódicas
try:
    from .celery_beat_config import get_beat_schedule
    celery_app.conf.beat_schedule = get_beat_schedule()
    logger.info("✅ Celery Beat schedule configurado")
except Exception as e:
    logger.warning(f"⚠️ Celery Beat schedule não configurado: {e}")

# ✅ IMPORTANTE: Importa tasks para registrá-las no Celery
# Isso garante que o worker reconheça as tasks ao inicializar
from . import celery_tasks  # noqa: F401
